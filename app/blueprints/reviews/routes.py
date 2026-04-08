from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.blueprints.reviews import bp
from app.blueprints.reviews.forms import ReviewForm, DisputeForm, ArbitrationForm, ReportForm
from app.extensions import db
from app.models.review import (
    Review, RatingDimension, RatingScore, ReviewImage,
    ReviewLike, ReviewReport, Dispute, DisputeEvidence,
)
from app.models.location import Location
from app.models.user import User, Role
from app.services.rbac import permission_required
from app.services.moderation_service import check_content
from app.services.notification_service import notify
from app.services.audit_service import log_event
from app.utils.file_storage import save_file
from app.utils.helpers import is_htmx_request, paginate_query


@bp.route('/')
@login_required
@permission_required('review.view')
def list_reviews():
    query = Review.query

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter_by(status='approved')

    location_id = request.args.get('location_id', type=int)
    if location_id:
        query = query.filter_by(location_id=location_id)

    coach_id = request.args.get('coach_id', type=int)
    if coach_id:
        query = query.filter_by(coach_id=coach_id)

    query = query.order_by(Review.created_at.desc())
    pagination = paginate_query(query)
    locations = Location.query.filter_by(is_active=True).all()
    dimensions = RatingDimension.query.filter_by(is_active=True).order_by(RatingDimension.sort_order).all()

    if is_htmx_request():
        return render_template('reviews/partials/_review_list.html',
                               reviews=pagination, dimensions=dimensions)

    return render_template('reviews/list.html', reviews=pagination,
                           locations=locations, dimensions=dimensions)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('review.create')
def create():
    form = ReviewForm()
    _populate_form_choices(form)
    dimensions = RatingDimension.query.filter_by(is_active=True).order_by(RatingDimension.sort_order).all()

    if form.validate_on_submit():
        review = Review(
            content=form.content.data,
            coach_id=form.coach_id.data or None,
            location_id=form.location_id.data,
            created_by=current_user.id,
            status='pending',
        )
        db.session.add(review)
        db.session.flush()

        for dim in dimensions:
            score_val = request.form.get(f'score_{dim.id}', type=int)
            if score_val and 1 <= score_val <= 5:
                score = RatingScore(review_id=review.id, dimension_id=dim.id, score=score_val)
                db.session.add(score)

        if form.images.data:
            for img_file in form.images.data:
                if img_file and img_file.filename:
                    path = save_file(img_file, 'review_images')
                    if path:
                        db.session.add(ReviewImage(review_id=review.id, file_path=path))

        db.session.commit()

        mod_item = check_content(review.content, 'review', review.id, current_user.id)
        if mod_item:
            flash('Your review has been submitted and is pending moderation.', 'info')
        else:
            review.status = 'approved'
            db.session.commit()
            flash('Review published.', 'success')

        log_event('review_created', user_id=current_user.id,
                  resource_type='review', resource_id=review.id)
        return redirect(url_for('reviews.detail', review_id=review.id))

    return render_template('reviews/form.html', form=form, dimensions=dimensions)


@bp.route('/<int:review_id>')
@login_required
@permission_required('review.view')
def detail(review_id):
    review = db.session.get(Review, review_id)
    if not review:
        flash('Review not found.', 'danger')
        return redirect(url_for('reviews.list_reviews'))

    dimensions = RatingDimension.query.filter_by(is_active=True).order_by(RatingDimension.sort_order).all()
    report_form = ReportForm()
    dispute_form = DisputeForm()
    user_liked = ReviewLike.query.filter_by(review_id=review.id, user_id=current_user.id).first() is not None

    return render_template('reviews/detail.html', review=review, dimensions=dimensions,
                           report_form=report_form, dispute_form=dispute_form, user_liked=user_liked)


@bp.route('/<int:review_id>/like', methods=['POST'])
@login_required
@permission_required('review.view')
def like(review_id):
    existing = ReviewLike.query.filter_by(review_id=review_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(ReviewLike(review_id=review_id, user_id=current_user.id))
    db.session.commit()

    review = db.session.get(Review, review_id)
    if is_htmx_request():
        user_liked = ReviewLike.query.filter_by(review_id=review_id, user_id=current_user.id).first() is not None
        return render_template('reviews/partials/_like_button.html', review=review, user_liked=user_liked)

    return redirect(url_for('reviews.detail', review_id=review_id))


@bp.route('/<int:review_id>/report', methods=['POST'])
@login_required
@permission_required('review.view')
def report(review_id):
    form = ReportForm()
    if form.validate_on_submit():
        rpt = ReviewReport(
            review_id=review_id,
            reported_by=current_user.id,
            reason=form.reason.data,
        )
        db.session.add(rpt)
        db.session.commit()

        check_content(form.reason.data, 'review', review_id, current_user.id)
        flash('Report submitted.', 'info')

    return redirect(url_for('reviews.detail', review_id=review_id))


@bp.route('/<int:review_id>/dispute', methods=['GET', 'POST'])
@login_required
@permission_required('review.dispute')
def dispute(review_id):
    form = DisputeForm()
    review = db.session.get(Review, review_id)
    if not review:
        flash('Review not found.', 'danger')
        return redirect(url_for('reviews.list_reviews'))

    if form.validate_on_submit():
        d = Dispute(
            review_id=review_id,
            initiated_by=current_user.id,
            statement=form.statement.data,
        )
        db.session.add(d)
        db.session.flush()

        if form.evidence.data:
            for ev_file in form.evidence.data:
                if ev_file and ev_file.filename:
                    path = save_file(ev_file, 'evidence')
                    if path:
                        db.session.add(DisputeEvidence(
                            dispute_id=d.id, uploaded_by=current_user.id,
                            file_path=path,
                        ))

        review.status = 'disputed'
        db.session.commit()

        log_event('dispute_created', user_id=current_user.id,
                  resource_type='dispute', resource_id=d.id)
        flash('Dispute submitted.', 'info')
        return redirect(url_for('reviews.detail', review_id=review_id))

    return render_template('reviews/dispute.html', form=form, review=review)


@bp.route('/dispute/<int:dispute_id>/arbitrate', methods=['GET', 'POST'])
@login_required
@permission_required('review.moderate')
def arbitrate(dispute_id):
    d = db.session.get(Dispute, dispute_id)
    if not d:
        flash('Dispute not found.', 'danger')
        return redirect(url_for('reviews.list_reviews'))

    form = ArbitrationForm()
    if form.validate_on_submit():
        d.arbitration_outcome = form.outcome.data
        d.arbitrated_by = current_user.id
        d.status = 'resolved'
        d.resolved_at = datetime.now(timezone.utc)
        db.session.commit()

        log_event('dispute_resolved', user_id=current_user.id,
                  resource_type='dispute', resource_id=d.id)

        notify(d.initiated_by, 'dispute_assigned',
               'Dispute resolved',
               f'Your dispute for review #{d.review_id} has been resolved.',
               link=url_for('reviews.detail', review_id=d.review_id))

        flash('Arbitration recorded.', 'success')
        return redirect(url_for('reviews.detail', review_id=d.review_id))

    return render_template('reviews/arbitrate.html', form=form, dispute=d)


def _populate_form_choices(form):
    locations = Location.query.filter_by(is_active=True).all()
    form.location_id.choices = [(l.id, l.name) for l in locations]

    coach_role = Role.query.filter_by(name='Coach').first()
    coaches = User.query.filter_by(is_active=True)
    if coach_role:
        coaches = coaches.filter_by(role_id=coach_role.id)
    form.coach_id.choices = [(0, '-- Any --')] + [(c.id, c.username) for c in coaches.all()]
