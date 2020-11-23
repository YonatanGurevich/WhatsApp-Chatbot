from flask import Flask, request
from twilio.rest import Client
import mysql.connector
import os
from twilio.twiml.messaging_response import MessagingResponse


def build_chat_bot(dictionary):
    database = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd=""
    )
    cursor = database.cursor()

    # Create schema

    business_id = dictionary['business_id']
    cursor.execute("CREATE SCHEMA IF NOT EXISTS `{}`;".format(business_id))

    # Create steps table

    cursor.execute("CREATE TABLE IF NOT EXISTS `{}`.steps ("
                   "`step_id` INT NOT NULL PRIMARY KEY,"
                   "`prompt` VARCHAR(255) NOT NULL);".format(business_id))

    for index, step in enumerate(dictionary['steps']):
        step_id = index+1
        prompt = step['prompt']

        cursor.execute("INSERT IGNORE INTO `{}`.`steps` VALUES ('{}', '{}');".format(business_id, step_id, prompt))
        database.commit()

        #  Create options table for each step

        cursor.execute("CREATE TABLE IF NOT EXISTS `{}`.`{}` ("
                       "`option_id` INT NOT NULL PRIMARY KEY,"
                       "`description` VARCHAR(45) NOT NULL);".format(business_id, step_id))
        for i, option in enumerate(step["options"]):
            option_id = i+1
            description = option
            cursor.execute("INSERT IGNORE INTO `{}`.`{}` VALUES ('{}', '{}');"
                           .format(business_id, step_id, option_id, description))
            database.commit()
    cursor.execute("CREATE SCHEMA IF NOT EXISTS `orders`")
    cursor.execute("CREATE TABLE IF NOT EXISTS `orders`.`{}` ("
                   "`step_id` INT NOT NULL PRIMARY KEY,"
                   "`question` VARCHAR(255) NOT NULL)"
                   .format(business_id))
    questions = get_questions(business_id)
    for index, question in enumerate(questions):
        cursor.execute("INSERT IGNORE INTO `orders`.`{}` VALUES ('{}', '{}');"
                       .format(business_id, int(index+1), question))
        database.commit()
    cursor.close()


def get_questions(schema):
    database = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="jonatan20081"
    )
    cursor = database.cursor()
    business = schema

    # queries:

    get_steps_table = "SELECT * FROM `{}`.`steps`".format(business)

    # format questions

    cursor.execute(get_steps_table)
    steps_table = cursor.fetchall()
    questions = []
    for index, step in enumerate(steps_table):
        cursor.execute("SELECT * FROM `{}`.`{}`".format(business, step[0]))
        options = cursor.fetchall()
        my_string = ""
        my_string += steps_table[index][1]
        for option in options:
            my_string += ("\n" + str(option[0]) + ")" + option[1])
        questions.append(my_string)
    return questions


def order(schema, client_num, message):
    database = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="jonatan20081"
    )
    cursor = database.cursor()
    cursor.execute('SELECT COUNT(*) FROM `orders`.`{}`'.format(schema))
    total_steps = cursor.fetchall()
    total_steps = total_steps[0][0]
    cursor.execute('CREATE TABLE IF NOT EXISTS `orders`.`{}` ('
                   'step_id INT NOT NULL DEFAULT 0 PRIMARY KEY,'
                   'answer INT NOT NULL DEFAULT 0);'.format(client_num))
    cursor.execute('SELECT COUNT(*) FROM `orders`.`{}`;'.format(client_num))
    steps = cursor.fetchall()
    steps = steps[0][0]

    # If its the first time (steps == 0) or a new order (steps > total steps needed to make an order)

    if steps == 0 or steps > total_steps:
        cursor.execute('TRUNCATE `orders`.`{}`;'.format(client_num))
        database.commit()
        cursor.execute('SELECT `question` FROM `orders`.`{}` WHERE step_id = 1;'.format(schema))
        question = cursor.fetchall()
        cursor.execute('INSERT INTO `orders`.`{}` (step_id) VALUES (1);'
                       .format(client_num))
        database.commit()
        return [str(question[0][0])]
    else:
        # Proceed from last step
        cursor.execute('SELECT step_id FROM `orders`.`{}` ORDER BY `step_id` DESC LIMIT 1;'.format(client_num))
        last_step = cursor.fetchall()
        cursor.execute('UPDATE `orders`.`{}` SET `answer` = {} WHERE `step_id` = {}'
                       .format(client_num, message, last_step[0][0]))
        database.commit()
        steps += 1
        cursor.execute('INSERT INTO `orders`.`{}` (step_id) VALUES ({});'
                       .format(client_num, steps))
        database.commit()
        cursor.execute('SELECT `question` FROM `orders`.`{}` WHERE step_id = {}'.format(schema, steps))
        question = cursor.fetchall()
        if len(question) == 0:
            cursor.execute('SELECT * FROM `orders`.`{}` ORDER BY step_id ASC'.format(client_num))
            fin = cursor.fetchall()
            return ["Your order is complete. Enjoy!", fin[0:total_steps]]
        else:
            return [str(question[0][0])]


app = Flask(__name__)

account_sid = os.environ.get('twilio_account_sid')
auth_token = os.environ.get('twilio_auth_token')

client = Client(account_sid, auth_token)
phone_number = 'whatsapp:+14155238886'


@app.route('/api/send/scheduledMessage', methods=['POST'])
def send_whatsapp():
    try:
        request_data = request.get_json()
        new_message = {
            'message_body': request_data['message_body'],
            'clients': request_data['clients']
        }
        for c in new_message['clients']:
            client.messages.create(
                body=new_message['message_body'],
                from_=phone_number,
                to=("whatsapp:" + c)
            )
        return "message sent", 200
    except Exception as e:
        return str(e), 500


@app.route('/api/chatbot/create', methods=['POST'])
def create_chatbot():
    try:
        request_data = request.get_json()
        build_chat_bot(request_data)
        return "finished successfully", 200
    except Exception as e:
        return str(e), 500


@app.route('/api/chatbot/conversation', methods=['POST'])
def conversation():
    try:
        resp = MessagingResponse()
        msg = request.form.get('Body')
        client_phone = request.form.get('From')
        business_phone = request.form.get('To')
        business = ""
        client_ = ""
        for i in business_phone:
            if i in '1234567890+':
                business += i
        for j in client_phone:
            if j in '1234567890+':
                client_ += j
        next_step = order(business, client_, msg)
        resp.message(next_step[0])
        # next step returns next question during conversation and an order dict in place[1] when order is finished
        if len(next_step) == 2:
            # TODO create actual order with next_step[1] (includes list of (step, answer))
            pass
        return str(resp), 200
    except Exception as e:
        return str(e), 500


app.run(port=5000)
