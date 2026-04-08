from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.blueprints.students import bp
from app.blueprints.students.forms import StudentForm, StudentNoteForm
from app.extensions import db
from app.models.student import Student, StudentNote
from app.models.location import Location
from app.models.user import User, Role
from app.services.rbac import permission_required
from app.services.audit_service import log_event
from app.services.notification_service import notify
from app.utils.helpers import is_htmx_request, paginate_query


@bp.route('/')
@login_required
@permission_required('student.view')
def list_students():
    query = Student.query

    if current_user.role.name == 'Coach':
        query = query.filter_by(assigned_coach_id=current_user.id)

    location_id = request.args.get('location_id', type=int)
    if location_id:
        query = query.filter_by(location_id=location_id)

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            db.or_(
                Student.first_name.ilike(f'%{search}%'),
                Student.last_name.ilike(f'%{search}%'),
                Student.email.ilike(f'%{search}%'),
            )
        )

    query = query.order_by(Student.created_at.desc())
    pagination = paginate_query(query)
    locations = Location.query.filter_by(is_active=True).all()

    if is_htmx_request():
        return render_template('students/partials/_student_table.html',
                               students=pagination, locations=locations)

    return render_template('students/list.html',
                           students=pagination, locations=locations)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('student.create')
def create():
    form = StudentForm()
    _populate_form_choices(form)

    if form.validate_on_submit():
        student = Student(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            date_of_birth=form.date_of_birth.data,
            address=form.address.data,
            license_number=form.license_number.data,
            status=form.status.data,
            location_id=form.location_id.data,
            assigned_coach_id=form.assigned_coach_id.data or None,
            handler_id=current_user.id,
        )
        db.session.add(student)
        db.session.commit()

        log_event('student_created', user_id=current_user.id,
                  resource_type='student', resource_id=student.id)

        if student.assigned_coach_id:
            notify(student.assigned_coach_id, 'registration_approved',
                   f'New student assigned: {student.full_name}',
                   f'Student {student.full_name} has been assigned to you.',
                   link=url_for('students.detail', student_id=student.id))

        flash('Student created successfully.', 'success')
        return redirect(url_for('students.detail', student_id=student.id))

    return render_template('students/form.html', form=form, title='New Student')


@bp.route('/<int:student_id>')
@login_required
@permission_required('student.view')
def detail(student_id):
    student = db.session.get(Student, student_id) or abort_404()

    if current_user.role.name == 'Coach' and student.assigned_coach_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('students.list_students'))

    note_form = StudentNoteForm()
    return render_template('students/detail.html', student=student, note_form=note_form)


@bp.route('/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('student.edit')
def edit(student_id):
    student = db.session.get(Student, student_id) or abort_404()
    form = StudentForm(obj=student)
    _populate_form_choices(form)

    if form.validate_on_submit():
        form.populate_obj(student)
        student.assigned_coach_id = form.assigned_coach_id.data or None
        db.session.commit()
        log_event('student_updated', user_id=current_user.id,
                  resource_type='student', resource_id=student.id)
        flash('Student updated.', 'success')
        return redirect(url_for('students.detail', student_id=student.id))

    return render_template('students/form.html', form=form, title='Edit Student', student=student)


@bp.route('/<int:student_id>/notes', methods=['POST'])
@login_required
@permission_required('student.add_note')
def add_note(student_id):
    student = db.session.get(Student, student_id) or abort_404()
    form = StudentNoteForm()

    if form.validate_on_submit():
        note = StudentNote(
            student_id=student.id,
            coach_id=current_user.id,
            content=form.content.data,
        )
        db.session.add(note)
        db.session.commit()
        log_event('student_note_added', user_id=current_user.id,
                  resource_type='student', resource_id=student.id)
        flash('Note added.', 'success')

    if is_htmx_request():
        return render_template('students/partials/_notes.html', student=student,
                               note_form=StudentNoteForm())

    return redirect(url_for('students.detail', student_id=student.id))


def _populate_form_choices(form):
    locations = Location.query.filter_by(is_active=True).all()
    form.location_id.choices = [(l.id, l.name) for l in locations]

    coach_role = Role.query.filter_by(name='Coach').first()
    coaches = User.query.filter_by(is_active=True)
    if coach_role:
        coaches = coaches.filter_by(role_id=coach_role.id)
    form.assigned_coach_id.choices = [(0, '-- None --')] + [
        (c.id, c.username) for c in coaches.all()
    ]


def abort_404():
    from flask import abort
    abort(404)
