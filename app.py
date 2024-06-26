from flask import Flask, flash, render_template, request, redirect, session
from urllib.parse import urlparse
import os
import psycopg2
import psycopg2.extras
import pymupdf
from datetime import datetime
from werkzeug.utils import secure_filename


UPLOAD_FOLDER = 'static/uploads/'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = ''  # inside the quotes is a random string


result = urlparse('') # inside the quotes is database URI
username = result.username
password = result.password
database = result.path[1:]
hostname = result.hostname
port = result.port
database_session = psycopg2.connect(
    database = database,
    user = username,
    password = password,
    host = hostname,
    port = port
)
cursor = database_session.cursor(cursor_factory=psycopg2.extras.DictCursor)

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = None
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        country = request.form.get('country')
        city = request.form.get('city')
        street = request.form.get('street')
        birth_date = request.form.get('birth_date')
        sex = request.form.get('sex')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        user_type = request.form.get('user_type')

        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        email_database = cursor.fetchone()
        if email_database is None:

            cursor.execute('INSERT INTO users(first_name, last_name, email, country, city, street, birth_date, sex, password, user_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
                          ,(first_name, last_name, email, country, city, street, birth_date, sex, password, user_type))
            database_session.commit()

            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user_id = cursor.fetchone()

            cursor.execute('INSERT INTO user_phone_number(user_id, phone_number) VALUES (%s, %s)'
                          ,(user_id['id'], phone_number))
            database_session.commit()

            if user_type == 'admin':
               cursor.execute('INSERT INTO admin(id) VALUES (%s)', (user_id['id'],))
               database_session.commit()
            elif user_type == 'doctor':
               cursor.execute('INSERT INTO doctor(id) VALUES (%s)', (user_id['id'],))
               database_session.commit()
            else:
               cursor.execute('INSERT INTO patient(id) VALUES (%s)', (user_id['id'],))
               database_session.commit()
            
            message = 'Thank you for registering. Please login.'

        else:
            message = 'Account already exists!'
    user = session.get('user')
    if user is None:
        return render_template('register.html', message=message)
    return redirect('/')


@app.route('/login', methods=['GET', 'POST'])
def login():
    message = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()
        if user is None:
            message = 'Invalid email or password.'
        else:
            session['user'] = dict(user)
            return redirect('/')
        
    user = session.get('user')
    if user is None:
        return render_template('login.html', message=message)
    return redirect('/')

@app.route('/')
def index():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    if user['user_type'] == 'admin':
        cursor.execute('SELECT * FROM doctor')
        doc_ids = cursor.fetchall()
        doctors_num = len(doc_ids)

        cursor.execute('SELECT * FROM patient')
        pat_ids = cursor.fetchall()
        patients_num = len(pat_ids)

        cursor.execute('SELECT * FROM contact_form')
        contacts = cursor.fetchall()
        contact_forms_num = len(contacts)
        return render_template('a_index.html', user=user, doctors_num=doctors_num, patients_num=patients_num, contact_forms_num=contact_forms_num)
    
    elif user['user_type'] == 'doctor':
        cursor.execute('SELECT * FROM time_slot WHERE doctor_id = %s', (user['id'],))
        time_slots = cursor.fetchall()
        appointments_list = []
        time_slots_list = []
        for slot in time_slots:
            cursor.execute('SELECT * FROM appointment WHERE id = %s', (slot['id'],))
            appointments_list.append(cursor.fetchone())

        cursor.execute('SELECT * FROM appointment')
        appointments = cursor.fetchall()
        busy_time_slots_ids = set()
        for appointment in appointments:
            busy_time_slots_ids.add(appointment['id'])
        cursor.execute('SELECT * FROM time_slot')
        free_time_slots = cursor.fetchall()
        busy_slots_list = []
        free_slots_list = []
        for slot in free_time_slots:
            if slot['id'] in busy_time_slots_ids:
                busy_slots_list.append(slot)
            else:
                free_slots_list.append(slot)
        my_busy_slots_list = []
        my_free_slots_list = []

        for slot in busy_slots_list:
            if slot['doctor_id'] == user['id']:
                my_busy_slots_list.append(slot)

        for slot in free_slots_list:
            if slot['doctor_id'] == user['id']:
                my_free_slots_list.append(slot)

        number_of_free_slots = len(my_free_slots_list)
        number_of_busy_slots = len(my_busy_slots_list)

        treated_patients_list = []
        cursor.execute('SELECT * FROM diagnosed_by WHERE doctor_id = %s', (user['id'],))
        treated_patients = cursor.fetchall()
        for patient in treated_patients:
            treated_patients_list.append(patient)
        treated_patients_num = len(treated_patients_list)

        return render_template('d_index.html', user=user, number_of_busy_slots=number_of_busy_slots, number_of_free_slots=number_of_free_slots, time_slots_list=time_slots_list, treated_patients_num=treated_patients_num)
    
    cursor.execute('SELECT * FROM appointment WHERE patient_id = %s', (user['id'],))
    appointments_ids = cursor.fetchall()
    appointments_count = len(appointments_ids)
    time_slots_list = []
    doctors_list = []
    for i in range(appointments_count):
        cursor.execute('SELECT * FROM time_slot WHERE id = %s', (appointments_ids[i]['id'],))
        time_slots_list.append(cursor.fetchone())
        cursor.execute('SELECT * FROM users WHERE id = %s', (time_slots_list[i]['doctor_id'],))
        doctors_list.append(cursor.fetchone())
        
    return render_template('p_index.html', user=user, appointments_count=appointments_count, time_slots_list=time_slots_list, doctors_list=doctors_list)

@app.route('/about')
def about():
    user = session.get('user')
    if user is None:
        return render_template('about.html')
    
    if user['user_type'] == 'admin':
        return render_template('a_index.html', user=user)
    
    elif user['user_type'] == 'doctor':
        return render_template('d_index.html', user=user)
    
    cursor.execute('SELECT * FROM appointment WHERE patient_id = %s', (user['id'],))
    appointments_ids = cursor.fetchall()
    appointments_count = len(appointments_ids)
    time_slots_list = []
    doctors_list = []
    for i in range(appointments_count):
        cursor.execute('SELECT * FROM time_slot WHERE id = %s', (appointments_ids[i]['id'],))
        time_slots_list.append(cursor.fetchone())
        cursor.execute('SELECT * FROM users WHERE id = %s', (time_slots_list[i]['doctor_id'],))
        doctors_list.append(cursor.fetchone())
        
    return render_template('p_index.html', user=user, appointments_count=appointments_count, time_slots_list=time_slots_list, doctors_list=doctors_list)

@app.route('/p_index')
def p_index():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM appointment WHERE patient_id = %s', (user['id'],))
    appt_ids = cursor.fetchall()
    appointments_count = len(appt_ids)
    time_slots_list = []
    doctors_list = []
    if appointments_count >= 1:
        for i in range(len(appt_ids)):
            cursor.execute('SELECT * FROM time_slot WHERE id = %s', (appt_ids[i]['id'],))
            time_slots_list.append(cursor.fetchone())
            cursor.execute('SELECT * FROM users WHERE id = %s', (time_slots_list[i]['doctor_id'],))
            doctors_list.append(cursor.fetchone())

    return render_template('p_index.html', user=user, appointments_count=appointments_count, time_slots_list=time_slots_list, doctors_list=doctors_list)

@app.route('/p_profile')
def p_profile():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM user_phone_number WHERE user_id = %s', (user['id'],))
    phone_numbers_list = cursor.fetchall()
    phone_numbers = []
    for num in phone_numbers_list:
        phone_numbers.append(num['phone_number'])

    return render_template('p_profile.html', user=user, phone_numbers=phone_numbers)

@app.route('/p_schedule_appointment', methods=['GET', 'POST'])
def p_schedule_appointment():
    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        user_id = request.form.get('user_id')
        doctor_id = request.form.get('doctor_id')

        cursor.execute('INSERT INTO appointment(id, patient_id) VALUES (%s, %s)', (slot_id, user_id))
        database_session.commit()

        cursor.execute('SELECT * FROM diagnosed_by WHERE doctor_id = %s AND patient_id = %s', (doctor_id, user_id))
        diagnosed_before = cursor.fetchone()
        if diagnosed_before is None:
            cursor.execute('INSERT INTO diagnosed_by(doctor_id, patient_id) VALUES (%s, %s)', (doctor_id, user_id))
            database_session.commit()

        return redirect('/')

    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM appointment')
    appointments = cursor.fetchall()
    busy_time_slots_ids = set()
    for appointment in appointments:
        busy_time_slots_ids.add(appointment['id'])
    cursor.execute('SELECT * FROM time_slot')
    free_time_slots = cursor.fetchall()
    free_slots_list = []
    for slot in free_time_slots:
        if slot['id'] in busy_time_slots_ids:
            continue
        free_slots_list.append(slot)

    number_of_free_slots = len(free_slots_list)
    doctors_list = []
    for i in range(number_of_free_slots):
        cursor.execute('SELECT * FROM users WHERE id = %s', (free_slots_list[i]['doctor_id'],))
        doctors_list.append(cursor.fetchone())

    return render_template('p_schedule_appointment.html', user=user, free_slots_list=free_slots_list, number_of_free_slots=number_of_free_slots, doctors_list=doctors_list)

@app.route('/p_upload_scan', methods=['GET', 'POST'])
def p_upload_scan():
    if request.method == 'POST':

        file = request.files['scan_file']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user_id = request.form.get('user_id')

        doc = pymupdf.open(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        page = doc[0]
        words = page.get_text('words', sort=True)

        doctor_id = ''
        date = ''
        findings = ''
        cost = ''
        scan_images = ''

        for i, word in enumerate(words):
            
            text = word[4]
            if text == 'Doctor_ID:':  
                doctor_id = words[i + 1][4]

            elif text == 'Date:':
                date = words[i + 1][4]

            elif text == 'Findings:':
                findings_list = words[i + 1][4].split('_')

            elif text == 'Cost:':
                cost = words[i + 1][4] 
                
            elif text == 'Scan_Images:':
                scan_images = words[i + 1][4] 

        for word in findings_list:
            findings += word
            findings += ' '
            
        cursor.execute('SELECT * FROM doctor WHERE id = %s', (doctor_id,))
        doctor = cursor.fetchone()
        if doctor is None:
            flash("Error! You uploaded a scan with a doctor id that doesn't work in this hospital!")
            return redirect('/')

        cursor.execute('INSERT INTO scan(doctor_id, patient_id, findings, date, cost, scan_images) VALUES (%s, %s, %s, %s, %s, %s)'
                          ,(doctor_id, user_id, findings, date, cost, scan_images))
        database_session.commit()
        return redirect('/')

    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    return render_template('p_upload_scan.html', user=user)

@app.route('/p_view_medical_file')
def p_view_medical_file():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM scan WHERE patient_id = %s', (user['id'],))
    scans_list = cursor.fetchall()
    scans = []
    for scan in scans_list:
        scans.append(scan)

    cursor.execute('SELECT * FROM diagnosed_by WHERE patient_id = %s', (user['id'],))
    diagnosed_list = cursor.fetchall()
    doctors_ids = []
    for diagnosed in diagnosed_list:
        doctors_ids.append(diagnosed['doctor_id'])
    
    doctors = []
    for doctor_id in doctors_ids:
        cursor.execute('SELECT * FROM users WHERE id = %s', (doctor_id,))
        doctors.append(cursor.fetchone())

    scans_count = len(scans)
    doctors_count = len(doctors)
    return render_template('p_view_medical_file.html', user=user, scans=scans, scans_count=scans_count, doctors=doctors, doctors_count=doctors_count)

@app.route('/p_fill_contact_form', methods=['GET', 'POST'])
def p_fill_contact_form():
    if request.method == 'POST':
        title = request.form.get('title')
        inquiry = request.form.get('inquiry')
        user_id = request.form.get('user_id')
        date = datetime.today().strftime('%Y-%m-%d')

        cursor.execute('INSERT INTO contact_form(title, request, date, patient_id) VALUES (%s, %s, %s, %s)'
                          ,(title, inquiry, date, user_id))
        database_session.commit()
        return redirect('/')
    
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    return render_template('p_fill_contact_form.html', user=user)

@app.route('/p_edit_profile', methods=['GET', 'POST'])
def p_edit_profile():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        country = request.form.get('country')
        city = request.form.get('city')
        street = request.form.get('street')
        birth_date = request.form.get('birth_date')
        new_phone_number = request.form.get('phone_number')
        deleted_phone_number = request.form.get('deleted_phone_number')
        user_id = request.form.get('user_id')
        
        if new_phone_number != '':
            cursor.execute('INSERT INTO user_phone_number(user_id, phone_number) VALUES (%s, %s)', (user_id, new_phone_number))
            database_session.commit()

        if deleted_phone_number != 'N':
            if deleted_phone_number != 'None':
                cursor.execute('DELETE FROM user_phone_number WHERE user_id = %s AND phone_number = %s', (user_id, deleted_phone_number))
                database_session.commit()
        
        old_email = session.get('user')['email']

        cursor.execute('UPDATE users SET first_name = %s, last_name = %s, email = %s, country = %s, city = %s, street = %s, birth_date = %s WHERE email = %s', (first_name, last_name, email, country, city, street, birth_date, old_email))
        database_session.commit()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        session['user'] = dict(cursor.fetchone())
        return redirect('/')
    
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM user_phone_number WHERE user_id = %s', (user['id'],))
    phone_numbers_list = cursor.fetchall()
    phone_numbers = []
    for num in phone_numbers_list:
        phone_numbers.append(num['phone_number'])
    
    return render_template('p_edit_profile.html', user=user, phone_numbers=phone_numbers)

@app.route('/a_index')
def a_index():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM doctor')
    doc_ids = cursor.fetchall()
    doctors_num = len(doc_ids)

    cursor.execute('SELECT * FROM patient')
    pat_ids = cursor.fetchall()
    patients_num = len(pat_ids)

    cursor.execute('SELECT * FROM contact_form')
    contacts = cursor.fetchall()
    contact_forms_num = len(contacts)


    return render_template('a_index.html', user=user, doctors_num=doctors_num, patients_num=patients_num, contact_forms_num=contact_forms_num)

@app.route('/a_profile')
def a_profile():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM user_phone_number WHERE user_id = %s', (user['id'],))
    phone_numbers_list = cursor.fetchall()
    phone_numbers = []
    for num in phone_numbers_list:
        phone_numbers.append(num['phone_number'])

    return render_template('a_profile.html', user=user, phone_numbers=phone_numbers)

@app.route('/a_appointments')
def a_appointments():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM appointment')
    appointments = cursor.fetchall()
    appointments_list = []
    for app in appointments:
        appointments_list.append(app)

    appointments_num = len(appointments_list)

    time_slots_list = []
    for i in range(len(appointments_list)):
        cursor.execute('SELECT * FROM time_slot WHERE id = %s', (appointments_list[i]['id'],))
        time_slots_list.append(cursor.fetchone())

    return render_template('a_appointments.html', user=user, appointments_list=appointments_list, time_slots_list=time_slots_list, appointments_num=appointments_num)

@app.route('/a_doctors', methods=['GET', 'POST'])
def a_doctors():
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        cursor.execute('DELETE FROM diagnosed_by WHERE doctor_id = %s', (doctor_id,))
        database_session.commit()
        cursor.execute('DELETE FROM doctor WHERE id = %s', (doctor_id,))
        database_session.commit()
        cursor.execute('DELETE FROM users WHERE id = %s', (doctor_id,))
        return redirect('/')


    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM doctor')
    doctors = cursor.fetchall()
    doctors_list = []
    for doctor in doctors:
        doctors_list.append(doctor)
    doctors_num = len(doctors_list)
    users_list = []
    for i in range(len(doctors_list)):
        cursor.execute('SELECT * FROM users WHERE id = %s', (doctors_list[i]['id'],))
        users_list.append(cursor.fetchone())
    
    return render_template('a_doctors.html', user=user, users_list=users_list, doctors_num=doctors_num)

@app.route('/a_patients', methods=['GET', 'POST'])
def a_patients():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        cursor.execute('DELETE FROM diagnosed_by WHERE patient_id = %s', (patient_id,))
        database_session.commit()
        cursor.execute('DELETE FROM patient WHERE id = %s', (patient_id,))
        database_session.commit()
        cursor.execute('DELETE FROM users WHERE id = %s', (patient_id,))
        return redirect('/')
    
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM patient')
    patients = cursor.fetchall()
    patients_list = []
    for patient in patients:
        patients_list.append(patient)
    patients_num = len(patients_list)
    users_list = []
    for i in range(len(patients_list)):
        cursor.execute('SELECT * FROM users WHERE id = %s', (patients_list[i]['id'],))
        users_list.append(cursor.fetchone())
    
    return render_template('a_patients.html', user=user, users_list=users_list, patients_num=patients_num)

@app.route('/a_view_inquiries')
def a_view_inquiries():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM contact_form')
    inquiries = cursor.fetchall()
    inquiries_list = []
    for inquiry in inquiries:
        inquiries_list.append(inquiry)
    return render_template('a_view_inquiries.html', user=user, inquiries_list=inquiries_list)


@app.route('/a_edit_profile', methods=['GET', 'POST'])
def a_edit_profile():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        country = request.form.get('country')
        city = request.form.get('city')
        street = request.form.get('street')
        birth_date = request.form.get('birth_date')
        new_phone_number = request.form.get('phone_number')
        deleted_phone_number = request.form.get('deleted_phone_number')
        user_id = request.form.get('user_id')
        
        if new_phone_number != '':
            cursor.execute('INSERT INTO user_phone_number(user_id, phone_number) VALUES (%s, %s)', (user_id, new_phone_number))
            database_session.commit()

        if deleted_phone_number != 'N':
            if deleted_phone_number != 'None':
                cursor.execute('DELETE FROM user_phone_number WHERE user_id = %s AND phone_number = %s', (user_id, deleted_phone_number))
                database_session.commit()
        
        old_email = session.get('user')['email']

        cursor.execute('UPDATE users SET first_name = %s, last_name = %s, email = %s, country = %s, city = %s, street = %s, birth_date = %s WHERE email = %s', (first_name, last_name, email, country, city, street, birth_date, old_email))
        database_session.commit()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        session['user'] = dict(cursor.fetchone())
        return redirect('/')
    
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM user_phone_number WHERE user_id = %s', (user['id'],))
    phone_numbers_list = cursor.fetchall()
    phone_numbers = []
    for num in phone_numbers_list:
        phone_numbers.append(num['phone_number'])
    
    return render_template('a_edit_profile.html', user=user, phone_numbers=phone_numbers)


@app.route('/d_index')
def d_index():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM time_slot WHERE doctor_id = %s', (user['id'],))
    time_slots = cursor.fetchall()
    appointments_list = []
    time_slots_list = []
    for slot in time_slots:
        cursor.execute('SELECT * FROM appointment WHERE id = %s', (slot['id'],))
        appointments_list.append(cursor.fetchone())
    appointments_count = len(appointments_list)

    cursor.execute('SELECT * FROM appointment')
    appointments = cursor.fetchall()
    busy_time_slots_ids = set()
    for appointment in appointments:
        busy_time_slots_ids.add(appointment['id'])
    cursor.execute('SELECT * FROM time_slot')
    free_time_slots = cursor.fetchall()
    free_slots_list = []
    for slot in free_time_slots:
        if slot['id'] in busy_time_slots_ids:
            continue
        free_slots_list.append(slot)
    my_free_slots_list = []
    for slot in free_slots_list:
        if slot['doctor_id'] == user['id']:
            my_free_slots_list.append(slot)

    number_of_free_slots = len(free_slots_list)

    treated_patients_list = []
    cursor.execute('SELECT * FROM diagnosed_by WHERE doctor_id = %s', (user['id'],))
    treated_patients = cursor.fetchall()
    for patient in treated_patients:
        treated_patients_list.append(patient)
    treated_patients_num = len(treated_patients_list)


    return render_template('d_index.html', user=user, appointments_count=appointments_count, number_of_free_slots=number_of_free_slots, treated_patients_num=treated_patients_num)

@app.route('/d_profile')
def d_profile():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM user_phone_number WHERE user_id = %s', (user['id'],))
    phone_numbers_list = cursor.fetchall()
    phone_numbers = []
    for num in phone_numbers_list:
        phone_numbers.append(num['phone_number'])

    return render_template('d_profile.html', user=user, phone_numbers=phone_numbers)

@app.route('/d_scheduled_appointments')
def d_scheduled_appointments():
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM time_slot WHERE doctor_id = %s', (user['id'],))
    time_slots = cursor.fetchall()
    appointments_list = []
    time_slots_list = []
    for slot in time_slots:
        cursor.execute('SELECT * FROM appointment WHERE id = %s', (slot['id'],))
        appointments_list.append(cursor.fetchone())

    for i in range(len(appointments_list)):
        if appointments_list[i] is None:
            continue
        cursor.execute('SELECT * FROM time_slot WHERE id = %s', (appointments_list[i]['id'],))
        time_slots_list.append(cursor.fetchone())
    appointments_count = len(time_slots_list)
    patients_list = []
    for time_slot in time_slots_list:
        cursor.execute('SELECT * FROM appointment WHERE id = %s', (time_slot['id'],))
        temp = cursor.fetchone()
        cursor.execute('SELECT * FROM users WHERE id = %s', (temp['patient_id'],))
        patients_list.append(cursor.fetchone())

    return render_template('d_scheduled_appointments.html', user=user, appointments_count=appointments_count, time_slots_list=time_slots_list, patients_list=patients_list)

@app.route('/d_time_slots', methods=['GET', 'POST'])
def d_time_slots():
    if request.method == 'POST':
        doctor_id = request.form.get('user_id')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        cursor.execute('INSERT INTO time_slot(doctor_id, date, start_time, end_time) VALUES (%s, %s, %s, %s)', (doctor_id, date, start_time, end_time))
        database_session.commit()
        return redirect('/')

    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM appointment')
    appointments = cursor.fetchall()
    busy_time_slots_ids = set()
    for appointment in appointments:
        busy_time_slots_ids.add(appointment['id'])
    cursor.execute('SELECT * FROM time_slot')
    free_time_slots = cursor.fetchall()
    free_slots_list = []
    for slot in free_time_slots:
        if slot['id'] in busy_time_slots_ids:
            continue
        free_slots_list.append(slot)
    my_free_slots_list = []
    for slot in free_slots_list:
        if slot['doctor_id'] == user['id']:
            my_free_slots_list.append(slot)

    number_of_free_slots = len(my_free_slots_list)
    doctors_list = []
    for i in range(number_of_free_slots):
        cursor.execute('SELECT * FROM users WHERE id = %s', (free_slots_list[i]['doctor_id'],))
        doctors_list.append(cursor.fetchone())
    
    return render_template('d_time_slots.html', user=user, my_free_slots_list=my_free_slots_list)


@app.route('/d_edit_profile', methods=['GET', 'POST'])
def d_edit_profile():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        country = request.form.get('country')
        city = request.form.get('city')
        street = request.form.get('street')
        birth_date = request.form.get('birth_date')
        new_phone_number = request.form.get('phone_number')
        deleted_phone_number = request.form.get('deleted_phone_number')
        user_id = request.form.get('user_id')
        
        if new_phone_number != '':
            cursor.execute('INSERT INTO user_phone_number(user_id, phone_number) VALUES (%s, %s)', (user_id, new_phone_number))
            database_session.commit()

        if deleted_phone_number != 'N':
            if deleted_phone_number != 'None':
                cursor.execute('DELETE FROM user_phone_number WHERE user_id = %s AND phone_number = %s', (user_id, deleted_phone_number))
                database_session.commit()
        
        old_email = session.get('user')['email']

        cursor.execute('UPDATE users SET first_name = %s, last_name = %s, email = %s, country = %s, city = %s, street = %s, birth_date = %s WHERE email = %s', (first_name, last_name, email, country, city, street, birth_date, old_email))
        database_session.commit()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        session['user'] = dict(cursor.fetchone())
        return redirect('/')
    
    user = session.get('user')
    if user is None:
        return render_template('index.html')
    
    cursor.execute('SELECT * FROM user_phone_number WHERE user_id = %s', (user['id'],))
    phone_numbers_list = cursor.fetchall()
    phone_numbers = []
    for num in phone_numbers_list:
        phone_numbers.append(num['phone_number'])
    
    return render_template('d_edit_profile.html', user=user, phone_numbers=phone_numbers)


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
