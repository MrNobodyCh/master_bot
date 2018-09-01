# -*- coding: utf-8 -*-
import ast
import logging
import sys
import time
from datetime import datetime, timedelta

import telebot
from telebot.apihelper import ApiException

import texts
from config import BotSettings, DBSettings
from getters import DBGetter, YClientsGetter, GooGl, UploadCareGetter

reload(sys)
sys.setdefaultencoding('utf-8')

logging.basicConfig(filename='debug.log', level=logging.INFO,
                    format="%(asctime)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S %p")

bot = telebot.TeleBot(BotSettings.TOKEN)
async_bot = telebot.AsyncTeleBot(BotSettings.TOKEN)
types = telebot.types

yclient_api = YClientsGetter()


def check_current_user_password(user_id):
    current_password = DBGetter(DBSettings.HOST).get("SELECT password FROM current_password")[0][0]
    try:
        logged_in_password = DBGetter(DBSettings.HOST).get("SELECT logged_password FROM authorized_users "
                                                           "WHERE user_id = %s" % user_id)[0][0]
    except IndexError:
        logged_in_password = current_password

    if logged_in_password == current_password:
        return "ok"
    else:
        return "changed"


def process_changed_password(message):
    user_id = message.chat.id
    bot.send_chat_action(chat_id=user_id, action="typing")
    password = message.text
    current_password = DBGetter(DBSettings.HOST).get("SELECT password FROM current_password")[0][0]
    if password == current_password:
        DBGetter(DBSettings.HOST).insert("UPDATE authorized_users SET logged_password ='%s' "
                                         "WHERE user_id = %s" % (password, user_id))
        staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                      "FROM masters WHERE user_id = %s" % user_id)[0]
        staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count "
                                                        "FROM masters WHERE user_id = %s" % user_id)[0][0]
        if staff_ids_count > 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            markup.row(texts.LOGOUT % staff_db_name)
            bot.send_message(chat_id=user_id, text=texts.PASSWORD_CORRECT, reply_markup=markup)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            bot.send_message(chat_id=user_id, text=texts.PASSWORD_CORRECT, reply_markup=markup)
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_INCORRECT)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.message_handler(commands=["my_records"])
def my_records_command(message):
    user_id = message.chat.id
    if check_current_user_password(user_id) == "ok":
        try:
            staff_id = DBGetter(DBSettings.HOST).get("SELECT staff_id FROM masters WHERE user_id = %s" % user_id)[0][0]
            records_list_menu(message)
        except IndexError:
            greeting_menu(message)
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.message_handler(commands=["start"])
def greeting_menu(message):
    user_id = message.chat.id
    first_name = message.chat.first_name
    bot.send_chat_action(chat_id=user_id, action="typing")
    user_auth = DBGetter(DBSettings.HOST).get("SELECT COUNT(*) FROM authorized_users "
                                              "WHERE user_id = %s" % user_id)[0][0]
    user_master = DBGetter(DBSettings.HOST).get("SELECT COUNT(*) FROM masters "
                                                "WHERE user_id = %s" % user_id)[0][0]
    # new user
    if user_auth == 0:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton(request_contact=True, text=texts.SEND_PHONE))
        bot.send_message(user_id, text=texts.GREETING % first_name, reply_markup=markup)

    # user present in DB
    # может быть авторизован (присутсвовать в authorized_users, но отсутсвовать в masters)
    if user_auth == 1 and user_master == 0:
        if check_current_user_password(user_id) == "ok":
            phone = DBGetter(DBSettings.HOST).get("SELECT phone FROM authorized_users "
                                                  "WHERE user_id = %s" % user_id)[0][0]
            password = DBGetter(DBSettings.HOST).get("SELECT logged_password FROM authorized_users "
                                                     "WHERE user_id = %s" % user_id)[0][0]
            staff_ids = {}
            for staff in yclient_api.get_all_staff():
                if str(staff["user"]["phone"]) == str(phone):
                    staff_ids.update({staff["name"]: staff["id"]})
            markup = types.InlineKeyboardMarkup()
            for k, v in staff_ids.iteritems():
                markup.add(
                    types.InlineKeyboardButton(text="%s" % k, callback_data="staff_%s_%s_%s" % (v, phone, password))
                    )
            bot.send_message(user_id, text=texts.STAFF_LIST, reply_markup=markup,
                             disable_notification=True, parse_mode="Markdown")
        else:
            msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
            bot.register_next_step_handler(msg, process_changed_password)

    if user_auth == 1 and user_master == 1:
        if check_current_user_password(user_id) == "ok":
            staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name FROM masters "
                                                          "WHERE user_id = %s" % user_id)[0]
            staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count FROM masters "
                                                            "WHERE user_id = %s" % user_id)[0][0]
            if staff_ids_count > 1:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(texts.MY_RECORDS)
                markup.row(texts.LOGOUT % staff_db_name)
                bot.send_message(chat_id=user_id, text=texts.WHAT_DO_WE_DO, reply_markup=markup)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(texts.MY_RECORDS)
                bot.send_message(chat_id=user_id, text=texts.WHAT_DO_WE_DO, reply_markup=markup)
        else:
            msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
            bot.register_next_step_handler(msg, process_changed_password)


@bot.message_handler(content_types=['contact'])
def process_phone_number(message):
    user_id = message.chat.id
    bot.send_chat_action(chat_id=user_id, action="typing")
    phone = message.contact.phone_number
    yclients_phones = []
    for staff in yclient_api.get_all_staff():
        try:
            if str(staff["user"]["phone"]) == str(phone):
                staff_id = staff["id"]
                yclients_phones.append(staff["user"]["phone"])
        except TypeError as error:
            logging.info("phone number processing error: {}".format(error))

    if yclients_phones.count(phone) != 0:
        msg = bot.send_message(chat_id=user_id, text=texts.PHONE_FOUND)
        bot.register_next_step_handler(msg, lambda m: process_password(m, staff_id, phone, yclients_phones))

    if yclients_phones.count(phone) == 0:
        msg = bot.send_message(chat_id=user_id, text=texts.TYPE_PHONE)
        bot.register_next_step_handler(msg, process_custom_phone_number)


def process_custom_phone_number(message):
    user_id = message.chat.id
    bot.send_chat_action(chat_id=user_id, action="typing")
    phone = message.text
    yclients_phones = []
    for staff in yclient_api.get_all_staff():
        if str(staff["user"]["phone"]) == str(phone):
            staff_id = staff["id"]
            yclients_phones.append(staff["user"]["phone"])

    if yclients_phones.count(phone) != 0:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        msg = bot.send_message(chat_id=user_id, text=texts.PHONE_FOUND, reply_markup=markup)
        bot.register_next_step_handler(msg, lambda m: process_password(m, staff_id, phone, yclients_phones))

    if yclients_phones.count(phone) == 0:
        msg = bot.send_message(chat_id=user_id, text=texts.TYPE_PHONE_AGAIN)
        bot.register_next_step_handler(msg, process_custom_phone_number)


def process_password(message, staff_id, phone, yclients_phones):
    user_id = message.chat.id
    bot.send_chat_action(chat_id=user_id, action="typing")
    password = message.text
    several_phones = set([x for x in yclients_phones if yclients_phones.count(x) > 1])
    current_password = DBGetter(DBSettings.HOST).get("SELECT password FROM current_password")[0][0]
    if password == current_password:
        # when one staff in yClients with this phone
        if len(several_phones) == 0:
            staff_name = yclient_api.get_staff_info(staff_id)["name"]
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            bot.send_message(chat_id=user_id, text=texts.AUTHORIZED % staff_name, reply_markup=markup)
            DBGetter(DBSettings.HOST).insert("INSERT INTO masters VALUES "
                                             "(%s, '%s', %s, %s)" % (user_id, staff_name, staff_id, 1))
            DBGetter(DBSettings.HOST).insert("INSERT INTO authorized_users (user_id, phone, logged_password, is_admin) "
                                             "VALUES (%s, '%s', '%s', FALSE )" % (user_id, phone, password))

        # when the several staff in yClients with this phone
        else:
            staff_ids = {}
            for staff in yclient_api.get_all_staff():
                if str(staff["user"]["phone"]) == str(phone):
                    staff_ids.update({staff["name"]: staff["id"]})
            markup = types.InlineKeyboardMarkup()
            for k, v in staff_ids.iteritems():
                markup.add(types.InlineKeyboardButton(text="%s" % k,
                                                      callback_data="staff_%s_%s_%s" % (v, phone, password)))
            bot.send_message(user_id, text=texts.STAFF_LIST, reply_markup=markup,
                             disable_notification=True, parse_mode="Markdown")
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_INCORRECT)
        bot.register_next_step_handler(msg, lambda m: process_password(m, staff_id, phone, yclients_phones))


@bot.message_handler(content_types=['text'], func=lambda message: message.text == texts.STAFF_LIST_MENU)
def staff_list_menu(message):
    user_id = message.chat.id
    if check_current_user_password(user_id) == "ok":
        bot.send_chat_action(chat_id=user_id, action="typing")
        phone = DBGetter(DBSettings.HOST).get("SELECT phone FROM authorized_users WHERE user_id = %s" % user_id)[0][0]
        password = DBGetter(DBSettings.HOST).get("SELECT logged_password FROM authorized_users "
                                                 "WHERE user_id = %s" % user_id)[0][0]
        staff_ids = {}
        for staff in yclient_api.get_all_staff():
            if str(staff["user"]["phone"]) == str(phone):
                staff_ids.update({staff["name"]: staff["id"]})
        markup = types.InlineKeyboardMarkup()
        for k, v in staff_ids.iteritems():
            markup.add(types.InlineKeyboardButton(text="%s" % k, callback_data="staff_%s_%s_%s" % (v, phone, password)))
        bot.send_message(user_id, text=texts.STAFF_LIST, reply_markup=markup,
                         disable_notification=True, parse_mode="Markdown")
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "staff")
def auth_staff_who_have_several_accounts(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        staff_id = call.data.split('_')[1]
        staff_info = yclient_api.get_staff_info(staff_id)
        staff_name = staff_info["name"]
        phone = call.data.split('_')[2]
        password = call.data.split('_')[3]
        DBGetter(DBSettings.HOST).insert("INSERT INTO authorized_users (user_id, phone, logged_password, is_admin) "
                                         "SELECT %s, '%s', '%s', %s WHERE NOT EXISTS "
                                         "(SELECT user_id, phone, logged_password, is_admin FROM authorized_users "
                                         "WHERE user_id = %s)" % (user_id, phone, password, False, user_id))

        DBGetter(DBSettings.HOST).insert("INSERT INTO masters (user_id, yclients_name, staff_id, staff_ids_count) "
                                         "SELECT %s, '%s', %s, %s WHERE NOT EXISTS "
                                         "(SELECT user_id, yclients_name, staff_id, staff_ids_count FROM masters "
                                         "WHERE user_id = %s)" % (user_id, staff_name, staff_id, 2, user_id))
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(texts.MY_RECORDS)
        markup.row(texts.LOGOUT % staff_name)
        try:
            bot.edit_message_text(chat_id=user_id, text=texts.AUTHORIZED_CALLBACK_ANSWER,
                                  message_id=call.message.message_id)
        except ApiException:
            pass
        bot.send_message(chat_id=user_id, text=texts.AUTHORIZED % staff_name, reply_markup=markup)
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.message_handler(content_types=['text'], func=lambda message: message.text.split()[0] == u"\U0001F6D1")
def logout_staff(message):
    user_id = message.chat.id
    if check_current_user_password(user_id) == "ok":
        bot.send_chat_action(chat_id=user_id, action="typing")
        try:
            staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                          "FROM masters WHERE user_id = %s" % user_id)[0]
            DBGetter(DBSettings.HOST).insert("DELETE FROM masters WHERE user_id = %s" % user_id)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.STAFF_LIST_MENU)
            bot.send_message(user_id, text=texts.LOGOUT_SUCCESS % staff_db_name, reply_markup=markup)
        except IndexError as error:
            logging.info("error during logout: {}. message: {}".format(error, message.text))
            pass
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.message_handler(content_types=['text'], func=lambda message: message.text == texts.MY_RECORDS)
def records_list_menu(message):
    user_id = message.chat.id
    if check_current_user_password(user_id) == "ok":
        bot.send_chat_action(chat_id=user_id, action="typing")
        staff_id = DBGetter(DBSettings.HOST).get("SELECT staff_id FROM masters WHERE user_id = %s" % user_id)[0][0]
        utc_datetime = datetime.utcnow()
        start_end_date = utc_datetime.strftime("%d-%m-%Y")
        records_list = yclient_api.get_records(staff_id=staff_id, start_date=start_end_date, end_date=start_end_date)
        records_list_sorted = sorted(records_list["data"], key=lambda item: item['datetime'])
        if records_list["count"] == 0:
            staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                          "FROM masters WHERE user_id = %s" % user_id)[0]
            staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count "
                                                            "FROM masters WHERE user_id = %s" % user_id)[0][0]
            if staff_ids_count > 1:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(texts.MY_RECORDS)
                markup.row(texts.LOGOUT % staff_db_name)
                bot.send_message(chat_id=user_id, text=texts.NO_RECORDS_TODAY)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(texts.MY_RECORDS)
                bot.send_message(chat_id=user_id, text=texts.NO_RECORDS_TODAY)
        else:
            for record in records_list_sorted:
                record_id = record["id"]
                record_datetime = record["datetime"]
                seance_length = record["seance_length"]
                seance_start_dt_obj = datetime.strptime(record_datetime, "%Y-%m-%dT%H:%M:%S+03:00")
                seance_start = datetime.strftime(seance_start_dt_obj, "%H:%M")
                seance_end_dt_obj = (seance_start_dt_obj + timedelta(seconds=seance_length))
                seance_end = datetime.strftime(seance_end_dt_obj, "%H:%M")
                record_comment = record["comment"]
                if record_comment != "":
                    record_comment = "(%s)" % record_comment
                else:
                    record_comment = ""
                # when main service not fill
                try:
                    service_name = record["services"][0]["title"]
                except IndexError:
                    service_name = "Без основной услуги"
                client_name = record["client"]["name"]
                visit_id = record["visit_id"]
                visit_info = yclient_api.get_specific_visit(visit_id)
                # when client not fill
                try:
                    if visit_info["records"] == 1:
                        visit_paid_status = visit_info["records"][0]["paid_full"]
                    else:
                        for visit in visit_info["records"]:
                            if u''.join(visit["services"][0]["title"]).encode('utf-8').strip() == service_name:
                                visit_paid_status = visit["paid_full"]
                except (KeyError, IndexError):
                    visit_paid_status = 0

                report_is_send = DBGetter(DBSettings.HOST).get("SELECT COUNT(*) FROM reports "
                                                               "WHERE record_id = %s" % record_id)[0][0]

                # report was not send, record marked as "attendance": 1, but visit no paid yet
                if record["attendance"] == 1 and visit_paid_status == 0 and report_is_send == 0:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(text=texts.SEND_REPORT,
                                                          callback_data="send_%s_%s" % (record_id, staff_id)))
                    bot.send_message(chat_id=user_id, text="%s-%s\n*%s*\n%s\n%s" % (seance_start, seance_end,
                                                                                    service_name, record_comment,
                                                                                    client_name),
                                     reply_markup=markup, parse_mode="Markdown")

                # report was send, record marked as "attendance": 1, but visit no paid yet
                if record["attendance"] == 1 and visit_paid_status == 0 and report_is_send == 1:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(text=texts.EDIT_REPORT,
                                                          callback_data="editreport_%s" % record_id))
                    bot.send_message(chat_id=user_id, text="%s-%s\n*%s*\n%s\n%s" % (seance_start, seance_end,
                                                                                    service_name, record_comment,
                                                                                    client_name),
                                     reply_markup=markup, parse_mode="Markdown")

                # new record, client in progress
                if record["attendance"] in (0, 2):
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton(text=texts.CLIENT_CAME, callback_data="yes_%s" % record_id),
                        types.InlineKeyboardButton(text=texts.CLIENT_NOT_CAME, callback_data="no_%s" % record_id)
                    )
                    bot.send_message(chat_id=user_id, text="%s-%s\n*%s*\n%s\n%s" % (seance_start, seance_end,
                                                                                    service_name, record_comment,
                                                                                    client_name),
                                     reply_markup=markup, parse_mode="Markdown")

                # report was send, record marked as "attendance": 1, visit paid
                if record["attendance"] == 1 and visit_paid_status == 1:
                    bot.send_message(chat_id=user_id, text="%s-%s\n*%s*\n%s\n%s\n%s" % (seance_start, seance_end,
                                                                                        service_name, record_comment,
                                                                                        client_name,
                                                                                        texts.VISIT_FINISHED),
                                     parse_mode="Markdown")

                # client not came
                if record["attendance"] == -1:
                    bot.send_message(chat_id=user_id, text="%s-%s\n*%s*\n%s\n%s\n%s" % (seance_start, seance_end,
                                                                                        service_name, record_comment,
                                                                                        client_name,
                                                                                        texts.VISIT_NOT_CAME),
                                     parse_mode="Markdown")
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] in ["yes", "no"])
def client_attendance_mark(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        record_id = int(call.data.split('_')[1])
        record_info = yclient_api.get_specific_record(record_id)
        try:
            seance_length = record_info["seance_length"]
            record_datetime = record_info["datetime"]
            record_comment = record_info["comment"]
            staff_id = DBGetter(DBSettings.HOST).get("SELECT staff_id FROM masters WHERE user_id = %s" % user_id)[0][0]
            client_info = {
                "phone": record_info["client"]["phone"],
                "name": record_info["client"]["name"],
                "email": record_info["client"]["email"],
            }
            services_info = record_info["services"]
            seance_start_dt_obj = datetime.strptime(record_datetime, "%Y-%m-%dT%H:%M:%S+03:00")
            seance_start = datetime.strftime(seance_start_dt_obj, "%H:%M")
            seance_end_dt_obj = (seance_start_dt_obj + timedelta(seconds=seance_length))
            seance_end = datetime.strftime(seance_end_dt_obj, "%H:%M")
            # when main service not fill
            try:
                service_name = record_info["services"][0]["title"]
            except IndexError:
                service_name = "Без основной услуги"
            try:
                if call.data.split('_')[0] == "yes":
                    yclient_api.change_record(record_id=record_id, staff_id=staff_id, services=services_info,
                                              client=client_info, datetime=record_datetime,
                                              seance_length=seance_length, comment=record_comment, attendance=1)
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(text=texts.SEND_REPORT,
                                                          callback_data="send_%s_%s" % (record_id, staff_id)))
                    bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id,
                                                  reply_markup=markup)
                    bot.answer_callback_query(call.id, text=texts.ACCEPTED)

                if call.data.split('_')[0] == "no":
                    yclient_api.change_record(record_id=record_id, staff_id=staff_id, services=services_info,
                                              client=client_info, datetime=record_datetime,
                                              seance_length=seance_length, comment=record_comment, attendance=-1)
                    bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id,
                                          text="%s-%s\n*%s*\n%s\n%s\n%s" % (seance_start, seance_end, service_name,
                                                                            client_info["name"], client_info["phone"],
                                                                            texts.VISIT_NOT_CAME),
                                          parse_mode="Markdown")
                    bot.answer_callback_query(call.id, text=texts.ACCEPTED)
            except ApiException:
                pass
        except KeyError:
            bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=texts.SEEMS_RECORD_DELETED)
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "send")
def prepare_report(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        record_id = int(call.data.split('_')[1])
        staff_id = int(call.data.split('_')[2])

        DBGetter(DBSettings.HOST).insert("INSERT INTO reports (record_id, staff_id) "
                                         "SELECT %s, %s WHERE NOT EXISTS (SELECT record_id, staff_id "
                                         "FROM reports WHERE record_id = %s)" % (record_id, staff_id, record_id))

        # show services
        service_category = yclient_api.get_service_categories()
        goods_category_id = int
        for category in service_category:
            if category["title"] == "Дополнительные услуги":
                goods_category_id = category["id"]
        services_list = {}
        for service in yclient_api.get_services():
            if service["category_id"] != goods_category_id:
                for staff in service["staff"]:
                    if staff["id"] == staff_id:
                        services_list.update({service["id"]: service["title"]})
        markup = types.InlineKeyboardMarkup()
        for service_id, service_title in services_list.iteritems():
            markup.add(types.InlineKeyboardButton(text="%s" % service_title,
                                                  callback_data="serviceadd_%s_%s" % (record_id, service_id)))
        bot.send_message(chat_id=user_id, text=texts.SELECT_SERVICE, reply_markup=markup, parse_mode="Markdown")

        # show additional services (goods)
        goods_list_to_show = {}
        goods_list = yclient_api.get_goods()
        for goods in goods_list:
            if goods["category"] == "Дополнительные услуги маникюр":
                goods_list_to_show.update({goods["good_id"]: [goods["title"], goods["cost"]]})
        bot.send_message(chat_id=user_id, text=texts.SELECT_ADDITIONAL_SERVICE, parse_mode="Markdown")
        for good_id, good_titles_costs in goods_list_to_show.iteritems():
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton(text="-", callback_data="goodrem_%s_%s_%s_%s" %
                                                                   (record_id, good_id, 0, good_titles_costs[1])),
                types.InlineKeyboardButton(text="0", callback_data="pass"),
                types.InlineKeyboardButton(text="+", callback_data="goodadd_%s_%s_%s_%s" %
                                                                   (record_id, good_id, 0, good_titles_costs[1]))
            )
            bot.send_message(chat_id=user_id, text="%s" % good_titles_costs[0],
                             reply_markup=markup, disable_web_page_preview=True)
        markup_photo = types.InlineKeyboardMarkup()
        markup_photo.row(types.InlineKeyboardButton(text=texts.ADD_PHOTO_BUTTON,
                                                    callback_data="addphoto_%s" % record_id))
        bot.send_message(chat_id=user_id, text=texts.ADD_PHOTO, reply_markup=markup_photo, parse_mode="Markdown")
        markup_comment = types.InlineKeyboardMarkup()
        markup_comment.row(types.InlineKeyboardButton(text=texts.LEAVE_COMMENT_BUT,
                                                      callback_data="comment_%s" % record_id))
        bot.send_message(chat_id=user_id, text=texts.LEAVE_COMMENT, reply_markup=markup_comment, parse_mode="Markdown")
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton(text=texts.DONE, callback_data="done_%s" % record_id))
        bot.send_message(chat_id=user_id, text=texts.PUSH_THE_BUTTON, reply_markup=markup, parse_mode="Markdown")
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "serviceadd")
def add_main_service(call):
    record_id = int(call.data.split('_')[1])
    service_id = int(call.data.split('_')[2])
    main_service_exists = DBGetter(DBSettings.HOST).get("SELECT service_id FROM reports "
                                                        "WHERE record_id = %s" % record_id)[0][0]
    if main_service_exists is None:
        DBGetter(DBSettings.HOST).insert("UPDATE reports SET service_id = %s "
                                         "WHERE record_id = %s" % (service_id, record_id))
        bot.answer_callback_query(call.id, text=texts.MAIN_SERVICE_ADDED)
    else:
        DBGetter(DBSettings.HOST).insert("UPDATE reports SET service_id = %s "
                                         "WHERE record_id = %s" % (service_id, record_id))
        bot.answer_callback_query(call.id, text=texts.MAIN_SERVICE_CHANGED)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] in ["goodrem", "goodadd"])
def add_goods(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        record_id = int(call.data.split('_')[1])
        good_id = int(call.data.split('_')[2])
        amount = call.data.split('_')[3]
        good_cost = call.data.split('_')[4]
        try:
            goods_transactions = ast.literal_eval(DBGetter(DBSettings.HOST).get(
                "SELECT goods_transactions FROM reports WHERE record_id = %s" % record_id)[0][0])
        except ValueError:
            goods_transactions = None

        if call.data.split('_')[0] == "goodrem":
            if amount != "0":
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton(
                        text="-", callback_data="goodrem_%s_%s_%s_%s" % (record_id, good_id,
                                                                         str((int(amount) - 1)), good_cost)),
                    types.InlineKeyboardButton(text="%s" % str((int(amount) - 1)), callback_data="pass"),
                    types.InlineKeyboardButton(
                        text="+", callback_data="goodadd_%s_%s_%s_%s" % (record_id, good_id,
                                                                         str((int(amount) - 1)), good_cost))
                )
                if goods_transactions is None:
                    goods_db = {good_id: [int(amount) - 1, int(good_cost)]}
                    DBGetter(DBSettings.HOST).insert("UPDATE reports SET goods_transactions = '%s' "
                                                     "WHERE record_id = %s" % (goods_db, record_id))
                else:
                    goods_transactions.update({good_id: [int(amount) - 1, int(good_cost)]})
                    if goods_transactions.get(good_id)[0] == 0:
                        goods_transactions.pop(good_id)
                    DBGetter(DBSettings.HOST).insert("UPDATE reports SET goods_transactions = '%s'"
                                                     "WHERE record_id = %s" % (goods_transactions, record_id))
                try:
                    bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id,
                                                  reply_markup=markup)
                    bot.answer_callback_query(call.id, text=texts.ADDITIONAL_SERVICE_REMOVED)
                except ApiException:
                    pass
            else:
                pass

        if call.data.split('_')[0] == "goodadd":
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton(
                    text="-", callback_data="goodrem_%s_%s_%s_%s" % (record_id, good_id,
                                                                     str((int(amount) + 1)), good_cost)),
                types.InlineKeyboardButton(text="%s" % str((int(amount) + 1)), callback_data="pass"),
                types.InlineKeyboardButton(
                    text="+",
                    callback_data="goodadd_%s_%s_%s_%s" % (record_id, good_id, str((int(amount) + 1)), good_cost))
            )
            if goods_transactions is None:
                goods_db = {good_id: [int(amount) + 1, int(good_cost)]}
                DBGetter(DBSettings.HOST).insert("UPDATE reports SET goods_transactions = '%s' "
                                                 "WHERE record_id = %s" % (goods_db, record_id))
            else:
                goods_transactions.update({good_id: [int(amount) + 1, int(good_cost)]})
                DBGetter(DBSettings.HOST).insert("UPDATE reports SET goods_transactions = '%s'"
                                                 "WHERE record_id = %s" % (goods_transactions, record_id))
            try:
                bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)
                bot.answer_callback_query(call.id, text=texts.ADDITIONAL_SERVICE_ADDED)
            except ApiException:
                pass
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "comment")
def master_comment(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        record_id = call.data.split('_')[1]
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(texts.CANCEL_OPERATION)
        msg = bot.send_message(user_id, text=texts.LEAVE_COMMENT_BELOW, reply_markup=markup)
        bot.register_next_step_handler(msg, lambda m: process_comment(m, record_id))
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


def process_comment(message, record_id):
    user_id = message.chat.id
    if message.text == texts.CANCEL_OPERATION:
        staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                      "FROM masters WHERE user_id = %s" % user_id)[0]
        staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count "
                                                        "FROM masters WHERE user_id = %s" % message.chat.id)[0][0]
        if staff_ids_count > 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            markup.row(texts.LOGOUT % staff_db_name)
            bot.send_message(chat_id=user_id, text="Отменено", reply_markup=markup)
        if staff_ids_count == 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            bot.send_message(chat_id=user_id, text="Отменено", reply_markup=markup)
    else:
        DBGetter(DBSettings.HOST).insert("UPDATE reports SET master_comment = '%s' "
                                         "WHERE record_id = %s" % (message.text, record_id))
        staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                      "FROM masters WHERE user_id = %s" % user_id)[0]
        staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count "
                                                        "FROM masters WHERE user_id = %s" % message.chat.id)[0][0]
        if staff_ids_count > 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            markup.row(texts.LOGOUT % staff_db_name)
            bot.send_message(chat_id=user_id, text=texts.COMMENT_SAVED, reply_markup=markup)
        if staff_ids_count == 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            bot.send_message(chat_id=user_id, text=texts.COMMENT_SAVED, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "done")
def show_report(call, record_id_back=None):
    try:
        user_id = call.message.chat.id
    except AttributeError:
        user_id = call.chat.id
    if check_current_user_password(user_id) == "ok":
        try:
            record_id = call.data.split('_')[1]
        except AttributeError:
            record_id = record_id_back
        main_service_id = DBGetter(DBSettings.HOST).get("SELECT service_id FROM reports "
                                                        "WHERE record_id = %s" % record_id)[0][0]
        report_photo = DBGetter(DBSettings.HOST).get("SELECT photo_id FROM reports "
                                                     "WHERE record_id = %s" % record_id)[0][0]
        if report_photo is not None:
            try:
                goods_to_show = {}
                goods_cost = 0
                goods = ast.literal_eval(DBGetter(DBSettings.HOST).get("SELECT goods_transactions FROM reports "
                                                                       "WHERE record_id = %s" % record_id)[0][0])
                for good_id, good_amount_cost in goods.iteritems():
                    specific_good = yclient_api.get_specific_good(good_id)
                    goods_cost += good_amount_cost[0] * good_amount_cost[1]
                    goods_to_show.update({specific_good["title"]: good_amount_cost[0]})
            except ValueError:
                goods_cost = 0
                goods_to_show = texts.NO

            if main_service_id is not None:
                record_info = yclient_api.get_specific_record(record_id)
                record_datetime = record_info["datetime"]
                client_info = {
                    "phone": record_info["client"]["phone"],
                    "name": record_info["client"]["name"],
                    "email": record_info["client"]["email"],
                }
                seance_start_dt_obj = datetime.strptime(record_datetime, "%Y-%m-%dT%H:%M:%S+03:00")
                seance_date = datetime.strftime(seance_start_dt_obj, "%Y-%m-%d")
                seance_start = datetime.strftime(seance_start_dt_obj, "%H:%M")
                photo = DBGetter(DBSettings.HOST).get("SELECT photo_id FROM reports WHERE record_id = %s" % record_id)[0][0]
                main_service_name = yclient_api.get_specific_service(main_service_id)["title"]
                main_service_cost = yclient_api.get_specific_service(main_service_id)["price_min"]
                master_comment_db = DBGetter(DBSettings.HOST).get("SELECT master_comment FROM reports "
                                                                  "WHERE record_id = %s" % record_id)[0][0]
                if master_comment_db is None:
                    master_comment_show = texts.NO
                else:
                    master_comment_show = master_comment_db

                if goods_to_show != texts.NO and goods_to_show != {}:
                    to_show_goods = []
                    for k, v in goods_to_show.iteritems():
                        to_show_goods.append("%s: %s\n" % (k, v))
                else:
                    to_show_goods = texts.NO

                final_cost = main_service_cost + goods_cost
                bot.send_message(chat_id=user_id, text=texts.YOUR_REPORT, parse_mode="Markdown")
                bot.send_photo(chat_id=user_id, photo=photo, caption=texts.PHOTO_OF_SERVICE)
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton(
                    text=texts.CHANGE_PHOTO, callback_data="changephoto_%s" % record_id)
                )
                markup.row(types.InlineKeyboardButton(
                    text=texts.SEND_DONE_REPORT, callback_data="sendreport_%s" % record_id)
                )
                bot.send_message(chat_id=user_id, text=texts.REPORT_RESULTS % (seance_date, seance_start,
                                                                               client_info["name"], main_service_name,
                                                                               ''.join(to_show_goods),
                                                                               master_comment_show, final_cost),
                                 reply_markup=markup)
            if main_service_id is None and goods_to_show not in [texts.NO, {}]:
                main_service_cost = 0
                main_service_name = texts.NO
                record_info = yclient_api.get_specific_record(record_id)
                record_datetime = record_info["datetime"]
                client_info = {
                    "phone": record_info["client"]["phone"],
                    "name": record_info["client"]["name"],
                    "email": record_info["client"]["email"],
                }
                seance_start_dt_obj = datetime.strptime(record_datetime, "%Y-%m-%dT%H:%M:%S+03:00")
                seance_date = datetime.strftime(seance_start_dt_obj, "%Y-%m-%d")
                seance_start = datetime.strftime(seance_start_dt_obj, "%H:%M")
                photo = DBGetter(DBSettings.HOST).get("SELECT photo_id FROM reports "
                                                      "WHERE record_id = %s" % record_id)[0][0]
                master_comment_db = DBGetter(DBSettings.HOST).get("SELECT master_comment FROM reports "
                                                                  "WHERE record_id = %s" % record_id)[0][0]
                if master_comment_db is None:
                    master_comment_show = texts.NO
                else:
                    master_comment_show = master_comment_db

                if goods_to_show != texts.NO and goods_to_show != {}:
                    to_show_goods = []
                    for k, v in goods_to_show.iteritems():
                        to_show_goods.append("%s: %s\n" % (k, v))
                else:
                    to_show_goods = texts.NO

                final_cost = main_service_cost + goods_cost
                bot.send_message(chat_id=user_id, text=texts.YOUR_REPORT, parse_mode="Markdown")
                bot.send_photo(chat_id=user_id, photo=photo, caption=texts.PHOTO_OF_SERVICE)
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton(text=texts.CHANGE_PHOTO,
                                                      callback_data="changephoto_%s" % record_id))
                markup.row(types.InlineKeyboardButton(text=texts.SEND_DONE_REPORT,
                                                      callback_data="sendreport_%s" % record_id))
                bot.send_message(chat_id=user_id, text=texts.REPORT_RESULTS % (seance_date, seance_start,
                                                                               client_info["name"], main_service_name,
                                                                               ''.join(to_show_goods),
                                                                               master_comment_show, final_cost),
                                 reply_markup=markup)
            if main_service_id is None and goods_to_show in [texts.NO, {}]:
                bot.send_message(chat_id=user_id, text=texts.ERROR_REPORT_RESULTS)
        else:
            bot.send_message(chat_id=user_id, text=texts.ERROR_REPORT_PHOTO)
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] in ["changephoto", "addphoto"])
def add_change_photo(call, record_id_back=None):
    try:
        user_id = call.message.chat.id
    except AttributeError:
        user_id = call.chat.id
    if check_current_user_password(user_id) == "ok":
        try:
            record_id = call.data.split('_')[1]
        except AttributeError:
            record_id = record_id_back
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(texts.CANCEL_OPERATION)
        msg = bot.send_message(user_id, text=texts.SEND_PHOTO, reply_markup=markup)
        bot.register_next_step_handler(msg, lambda m: process_photo(m, record_id))
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


def process_photo(message, record_id):
    if message.text == texts.CANCEL_OPERATION:
        staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                      "FROM masters WHERE user_id = %s" % message.chat.id)[0]
        staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count "
                                                        "FROM masters WHERE user_id = %s" % message.chat.id)[0][0]
        if staff_ids_count > 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            markup.row(texts.LOGOUT % staff_db_name)
            bot.send_message(chat_id=message.chat.id, text="Отменено", reply_markup=markup)
        if staff_ids_count == 1:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(texts.MY_RECORDS)
            bot.send_message(chat_id=message.chat.id, text="Отменено", reply_markup=markup)
    else:
        try:
            # process photo and add it to DB
            file_id = str(message.photo[-1].file_id)
            photo_path = bot.get_file(file_id).file_path
            telegram_photo_url = "https://api.telegram.org/file/bot{}/{}".format(BotSettings.TOKEN, photo_path)
            uploaded_photo = UploadCareGetter().upload_photo(photo_url=telegram_photo_url)
            short_photo_url = GooGl().short_link(uploaded_photo)
            DBGetter(DBSettings.HOST).insert("UPDATE reports SET photo = '%s', photo_id = '%s' "
                                             "WHERE record_id = %s" % (short_photo_url, file_id, record_id))
            staff_db_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name "
                                                          "FROM masters WHERE user_id = %s" % message.chat.id)[0]
            staff_ids_count = DBGetter(DBSettings.HOST).get("SELECT staff_ids_count "
                                                            "FROM masters WHERE user_id = %s" % message.chat.id)[0][0]
            if staff_ids_count > 1:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(texts.MY_RECORDS)
                markup.row(texts.LOGOUT % staff_db_name)
                bot.send_message(chat_id=message.chat.id, text=texts.PHOTO_CHANGED, reply_markup=markup)
            if staff_ids_count == 1:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row(texts.MY_RECORDS)
                bot.send_message(chat_id=message.chat.id, text=texts.PHOTO_CHANGED, reply_markup=markup)
        except Exception as error:
            bot.send_message(message.chat.id, text=texts.ERROR_DURING_PHOTO_ADD)
            time.sleep(1)
            add_change_photo(message, record_id)
            logging.error("Error during photo processing: %s" % error)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "sendreport")
def send_report_to_yclients(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        record_id = call.data.split('_')[1]
        record_info = yclient_api.get_specific_record(record_id)
        client_info = {
            "phone": record_info["client"]["phone"],
            "name": record_info["client"]["name"],
            "email": record_info["client"]["email"],
        }
        record_datetime = record_info["datetime"]
        seance_start_dt_obj = datetime.strptime(record_datetime, "%Y-%m-%dT%H:%M:%S+03:00")
        day = datetime.strftime(seance_start_dt_obj, "%Y-%m-%d")
        visit_date = datetime.strftime(seance_start_dt_obj, "%H:%M")
        visit_id = record_info["visit_id"]
        staff_id = DBGetter(DBSettings.HOST).get("SELECT staff_id FROM masters WHERE user_id = %s" % user_id)[0][0]
        staff_name = DBGetter(DBSettings.HOST).get("SELECT yclients_name FROM masters "
                                                   "WHERE user_id = %s" % user_id)[0][0]
        master_comment_db = DBGetter(DBSettings.HOST).get("SELECT master_comment FROM reports "
                                                          "WHERE record_id = %s" % record_id)[0][0]
        photo = DBGetter(DBSettings.HOST).get("SELECT photo FROM reports WHERE record_id = %s" % record_id)[0][0]
        main_service_id = DBGetter(DBSettings.HOST).get("SELECT service_id FROM reports "
                                                        "WHERE record_id = %s" % record_id)[0][0]
        if master_comment_db is None:
            master_comment_for_goods = photo
            master_comment_channel = texts.NO
        else:
            master_comment_for_goods = "{}. Фото работы: {}".format(master_comment_db, photo)
            master_comment_channel = master_comment_db

        try:
            goods_to_show = {}
            goods_cost = 0
            goods_db = ast.literal_eval(DBGetter(DBSettings.HOST).get("SELECT goods_transactions FROM reports "
                                                                      "WHERE record_id = %s" % record_id)[0][0])
            for good_id, good_amount_cost in goods_db.iteritems():
                specific_good = yclient_api.get_specific_good(good_id)
                goods_cost += good_amount_cost[0] * good_amount_cost[1]
                goods_to_show.update({specific_good["title"]: good_amount_cost[0]})
        except ValueError:
            goods_db = None
            goods_to_show = texts.NO

        if main_service_id is None and goods_db not in [None, {}]:
            # prepare goods info
            goods_transactions = []
            goods_cost_sum = 0
            if goods_db is not None and goods_db != {}:
                storage_id = int
                for storage in YClientsGetter().get_storages():
                    if storage["title"] == "Товары":
                        storage_id = storage["id"]
                for good_id, good_amount_cost in goods_db.iteritems():
                    good_cost = good_amount_cost[1]
                    goods_cost_sum += good_amount_cost[0] * good_amount_cost[1]
                    goods_transactions.append({
                        "good_id": good_id,
                        "storage_id": storage_id,
                        "amount": good_amount_cost[0],
                        "type": 1,
                        "master_id": staff_id,
                        "discount": 0,
                        "price": good_cost,
                        "cost": good_cost
                    })

            # prepare goods info for the channel
            to_show_goods = []
            for k, v in goods_to_show.iteritems():
                to_show_goods.append("%s: %s\n" % (k, v))

            # change visit details: add goods (if no goods, just add a comment)
            send_goods = yclient_api.change_visit(record_id=record_id, visit_id=visit_id,
                                                  goods_transactions=goods_transactions,
                                                  comment=master_comment_for_goods)
            if isinstance(send_goods, dict) and send_goods.get('meta'):
                bot.answer_callback_query(call.id, text=texts.REPORT_NOT_SEND)
                bot.send_message(chat_id=user_id, text=texts.SOMETHING_WENT_WRONG)
                logging.error("error during add goods: {}".format(send_goods.get('meta', {}).get('message', '')))
            else:
                DBGetter(DBSettings.HOST).insert("UPDATE reports SET day = '%s', visit_date = '%s', visit_id = %s, "
                                                 "is_send = TRUE, first_cost = %s, cost = %s "
                                                 "WHERE record_id = %s" % (day, visit_date, visit_id, goods_cost_sum,
                                                                           goods_cost_sum, record_id))
                try:
                    bot.answer_callback_query(call.id, text=texts.REPORT_WAS_SEND)
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(text=texts.REPORT_WAS_SEND, callback_data="pass"))
                    bot.edit_message_reply_markup(chat_id=user_id, reply_markup=markup,
                                                  message_id=call.message.message_id)
                    bot.send_message(chat_id=user_id, text=texts.REPORT_AFTER_SEND_INFO)
                    # send report to the channel
                    bot.send_message(chat_id=BotSettings.CHANNEL_REPORTS,
                                     text=texts.REPORT_RESULTS_CHANNEL % (staff_name, photo, day, visit_date,
                                                                          client_info["name"], texts.NO,
                                                                          ''.join(to_show_goods),
                                                                          master_comment_channel, goods_cost_sum))
                except ApiException:
                    pass
                logging.info("finished add goods to record with record_id: {}".format(record_id))

        if main_service_id is not None and goods_db not in [None, {}]:
            # prepare goods info
            goods_transactions = []
            goods_cost_sum = 0
            if goods_db is not None and goods_db != {}:
                storage_id = int
                for storage in YClientsGetter().get_storages():
                    if storage["title"] == "Товары":
                        storage_id = storage["id"]
                for good_id, good_amount_cost in goods_db.iteritems():
                    good_cost = good_amount_cost[1]
                    goods_cost_sum += good_amount_cost[0] * good_amount_cost[1]
                    goods_transactions.append({
                        "good_id": good_id,
                        "storage_id": storage_id,
                        "amount": good_amount_cost[0],
                        "type": 1,
                        "master_id": staff_id,
                        "discount": 0,
                        "price": good_cost,
                        "cost": good_cost
                    })

            # prepare goods info for the channel
            to_show_goods = []
            for k, v in goods_to_show.iteritems():
                to_show_goods.append("%s: %s\n" % (k, v))

            # change visit details: add goods (if no goods, just add a comment)
            send_goods = yclient_api.change_visit(record_id=record_id, visit_id=visit_id,
                                                  goods_transactions=goods_transactions,
                                                  comment=master_comment_for_goods)
            if isinstance(send_goods, dict) and send_goods.get('meta'):
                bot.answer_callback_query(call.id, text=texts.REPORT_NOT_SEND)
                bot.send_message(chat_id=user_id, text=texts.SOMETHING_WENT_WRONG)
                logging.error("error during add goods: {}".format(send_goods.get('meta', {}).get('message', '')))
            else:
                logging.info("finished add goods to record with record_id: {}".format(record_id))

            # prepare main service
            record_info = yclient_api.get_specific_record(record_id)
            record_datetime = record_info["datetime"]
            client_info = {
                "phone": record_info["client"]["phone"],
                "name": record_info["client"]["name"],
                "email": record_info["client"]["email"],
            }
            seance_length = record_info["seance_length"]
            record_comment = record_info["comment"]
            main_service_info = yclient_api.get_specific_service(main_service_id)
            main_service_name = main_service_info["title"]
            main_service_cost = main_service_info["price_min"]
            services_info = [{
                    "discount": 0,
                    "cost": main_service_cost,
                    "first_cost": main_service_cost,
                    "id": main_service_id
                }]
            final_cost = goods_cost_sum + main_service_cost
            # add main service to the record
            change_request = yclient_api.change_record(record_id=record_id, staff_id=staff_id, services=services_info,
                                                       client=client_info, datetime=record_datetime, attendance=1,
                                                       seance_length=seance_length, comment=record_comment)
            if isinstance(change_request, dict) and change_request.get('errors'):
                bot.answer_callback_query(call.id, text=texts.REPORT_NOT_SEND)
                bot.send_message(chat_id=user_id, text=texts.SOMETHING_WENT_WRONG)
                logging.error("error add service: {}".format(change_request.get('errors', {}).get('message', '')))
            else:
                DBGetter(DBSettings.HOST).insert("UPDATE reports SET day = '%s', visit_date = '%s', visit_id = %s, "
                                                 "is_send = TRUE, first_cost = %s, cost = %s "
                                                 "WHERE record_id = %s" % (day, visit_date, visit_id, final_cost,
                                                                           final_cost, record_id))
                try:
                    bot.answer_callback_query(call.id, text=texts.REPORT_WAS_SEND)
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(text=texts.REPORT_WAS_SEND, callback_data="pass"))
                    bot.edit_message_reply_markup(chat_id=user_id, reply_markup=markup,
                                                  message_id=call.message.message_id)
                    bot.send_message(chat_id=user_id, text=texts.REPORT_AFTER_SEND_INFO)
                    # send report to the channel
                    bot.send_message(chat_id=BotSettings.CHANNEL_REPORTS,
                                     text=texts.REPORT_RESULTS_CHANNEL % (staff_name, photo, day, visit_date,
                                                                          client_info["name"], main_service_name,
                                                                          ''.join(to_show_goods),
                                                                          master_comment_channel, final_cost))
                except ApiException:
                    pass
                logging.info("finished add service to record with record_id: {}".format(change_request["id"]))

        if main_service_id is not None and goods_db in [None, {}]:
            # prepare main service
            record_info = yclient_api.get_specific_record(record_id)
            record_datetime = record_info["datetime"]
            client_info = {
                "phone": record_info["client"]["phone"],
                "name": record_info["client"]["name"],
                "email": record_info["client"]["email"],
            }
            seance_length = record_info["seance_length"]
            record_comment = record_info["comment"]
            main_service_info = yclient_api.get_specific_service(main_service_id)
            main_service_name = main_service_info["title"]
            main_service_cost = main_service_info["price_min"]
            services_info = [{
                "discount": 0,
                "cost": main_service_cost,
                "first_cost": main_service_cost,
                "id": main_service_id
            }]

            # change visit details: add goods (if no goods, just add a comment)
            send_goods = yclient_api.change_visit(record_id=record_id, visit_id=visit_id,
                                                  goods_transactions=[],
                                                  comment=master_comment_for_goods)
            if isinstance(send_goods, dict) and send_goods.get('meta'):
                bot.answer_callback_query(call.id, text=texts.REPORT_NOT_SEND)
                bot.send_message(chat_id=user_id, text=texts.SOMETHING_WENT_WRONG)
                logging.error("error during add goods: {}".format(send_goods.get('meta', {}).get('message', '')))
            else:
                logging.info("finished add goods to record with record_id: {}".format(record_id))

            # add main service to the record
            change_request = yclient_api.change_record(record_id=record_id, staff_id=staff_id, services=services_info,
                                                       client=client_info, datetime=record_datetime, attendance=1,
                                                       seance_length=seance_length, comment=record_comment)
            if isinstance(change_request, dict) and change_request.get('errors'):
                bot.answer_callback_query(call.id, text=texts.REPORT_NOT_SEND)
                bot.send_message(chat_id=user_id, text=texts.SOMETHING_WENT_WRONG)
                logging.error("error add service: {}".format(change_request.get('errors', {}).get('message', '')))
            else:
                DBGetter(DBSettings.HOST).insert("UPDATE reports SET day = '%s', visit_date = '%s', visit_id = %s, "
                                                 "is_send = TRUE, first_cost = %s, cost = %s "
                                                 "WHERE record_id = %s" % (day, visit_date, visit_id, main_service_cost,
                                                                           main_service_cost, record_id))
                try:
                    bot.answer_callback_query(call.id, text=texts.REPORT_WAS_SEND)
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(text=texts.REPORT_WAS_SEND, callback_data="pass"))
                    bot.edit_message_reply_markup(chat_id=user_id, reply_markup=markup,
                                                  message_id=call.message.message_id)
                    bot.send_message(chat_id=user_id, text=texts.REPORT_AFTER_SEND_INFO)
                    # send report to the channel
                    bot.send_message(chat_id=BotSettings.CHANNEL_REPORTS,
                                     text=texts.REPORT_RESULTS_CHANNEL % (staff_name, photo, day, visit_date,
                                                                          client_info["name"], main_service_name,
                                                                          texts.NO, master_comment_channel,
                                                                          main_service_cost))
                except ApiException:
                    pass
                logging.info("finished add service to record with record_id: {}".format(change_request["id"]))
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == "editreport")
def edit_report(call):
    user_id = call.message.chat.id
    if check_current_user_password(user_id) == "ok":
        record_id = call.data.split('_')[1]
        staff_id = DBGetter(DBSettings.HOST).get("SELECT staff_id FROM reports WHERE record_id = %s" % record_id)[0][0]
        record = yclient_api.get_specific_record(record_id)
        visit_id = record["visit_id"]
        visit_info = yclient_api.get_specific_visit(visit_id)
        record_datetime = record["datetime"]
        seance_length = record["seance_length"]
        seance_start_dt_obj = datetime.strptime(record_datetime, "%Y-%m-%dT%H:%M:%S+03:00")
        seance_start = datetime.strftime(seance_start_dt_obj, "%H:%M")
        seance_end_dt_obj = (seance_start_dt_obj + timedelta(seconds=seance_length))
        seance_end = datetime.strftime(seance_end_dt_obj, "%H:%M")
        client_name = record["client"]["name"]
        # when main service not fill
        try:
            service_name = record["services"][0]["title"]
        except IndexError:
            service_name = "Без основной услуги"
        # when client not fill
        try:
            if visit_info["records"] == 1:
                visit_paid_status = visit_info["records"][0]["paid_full"]
            else:
                for visit in visit_info["records"]:
                    if u''.join(visit["services"][0]["title"]).encode('utf-8').strip() == service_name:
                        visit_paid_status = visit["paid_full"]
        except (KeyError, IndexError):
            visit_paid_status = 0

        if visit_paid_status == 0:
            # show services
            service_category = yclient_api.get_service_categories()
            goods_category_id = int
            for category in service_category:
                if category["title"] == "Дополнительные услуги":
                    goods_category_id = category["id"]
            services_list = {}
            for service in yclient_api.get_services():
                if service["category_id"] != goods_category_id:
                    for staff in service["staff"]:
                        if staff["id"] == staff_id:
                            services_list.update({service["id"]: service["title"]})
            markup = types.InlineKeyboardMarkup()
            for service_id, service_title in services_list.iteritems():
                markup.add(types.InlineKeyboardButton(text="%s" % service_title,
                                                      callback_data="serviceadd_%s_%s" % (record_id, service_id)))
            bot.send_message(call.message.chat.id, text=texts.SELECT_SERVICE,
                             reply_markup=markup, parse_mode="Markdown")

            # show additional services (goods)
            goods_list_to_show = {}
            goods_list = yclient_api.get_goods()
            for goods in goods_list:
                if goods["category"] == "Дополнительные услуги маникюр":
                    goods_list_to_show.update({goods["good_id"]: [goods["title"], goods["cost"]]})
            try:
                goods_db = ast.literal_eval(DBGetter(DBSettings.HOST).get("SELECT goods_transactions FROM reports "
                                                                          "WHERE record_id = %s" % record_id)[0][0])
            except ValueError:
                goods_db = None
            bot.send_message(call.message.chat.id, text=texts.SELECT_ADDITIONAL_SERVICE, parse_mode="Markdown")
            for good_id, good_titles_costs in goods_list_to_show.iteritems():
                if goods_db not in [None, {}]:
                    try:
                        goods_db_amount = goods_db.get(int(good_id))[0]
                    except TypeError:
                        goods_db_amount = 0
                else:
                    goods_db_amount = 0
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton(text="-", callback_data="goodrem_%s_%s_%s_%s" %
                                                                       (record_id, good_id, goods_db_amount,
                                                                        good_titles_costs[1])),
                    types.InlineKeyboardButton(text="%s" % str(goods_db_amount), callback_data="pass"),
                    types.InlineKeyboardButton(text="+", callback_data="goodadd_%s_%s_%s_%s" %
                                                                       (record_id, good_id, goods_db_amount,
                                                                        good_titles_costs[1]))
                )
                bot.send_message(call.message.chat.id, text="%s" % good_titles_costs[0],
                                 reply_markup=markup, disable_web_page_preview=True)
            markup_photo = types.InlineKeyboardMarkup()
            markup_photo.row(
                types.InlineKeyboardButton(text=texts.CHANGE_PHOTO_BUT, callback_data="changephoto_%s" % record_id))
            bot.send_message(chat_id=user_id, text=texts.CHANGE_PHOTO_EDIT,
                             reply_markup=markup_photo, parse_mode="Markdown")
            markup_comment = types.InlineKeyboardMarkup()
            markup_comment.row(
                types.InlineKeyboardButton(text=texts.LEAVE_COMMENT_BUT, callback_data="comment_%s" % record_id))
            bot.send_message(chat_id=user_id, text=texts.LEAVE_COMMENT, reply_markup=markup_comment,
                             parse_mode="Markdown")
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(text=texts.DONE, callback_data="done_%s" % record_id))
            bot.send_message(call.message.chat.id, text=texts.PUSH_THE_BUTTON,
                             reply_markup=markup, parse_mode="Markdown")
        else:
            bot.edit_message_text(chat_id=user_id, text="%s-%s\n*%s*\n%s\n%s" % (seance_start, seance_end,
                                                                                 service_name, client_name,
                                                                                 texts.VISIT_FINISHED),
                                  parse_mode="Markdown", message_id=call.message.message_id)
            bot.send_message(chat_id=user_id, text=texts.VISIT_ALREADY_PAID)
    else:
        msg = bot.send_message(chat_id=user_id, text=texts.PASSWORD_WAS_CHANGED)
        bot.register_next_step_handler(msg, process_changed_password)

while True:

    try:

        bot.polling(none_stop=True)

    # ConnectionError and ReadTimeout because of possible timeout of the requests library

    # TypeError for moviepy errors

    # maybe there are others, therefore Exception

    except Exception as e:
        logging.error(e)
        time.sleep(5)
