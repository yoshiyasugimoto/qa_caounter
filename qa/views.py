# coding:utf-8

import datetime
import json
import os

import requests
from flask import request, Blueprint
from sqlalchemy import create_engine, Column, String, Integer, MetaData, desc, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from attendance_manage.views import WorkTime


DB_CONNECT = os.environ.get('DB_CONNECT')

WEB_HOOK_URL = os.environ.get('WEB_HOOK_URL')

engine = create_engine(DB_CONNECT, poolclass=NullPool)

meta = MetaData(engine, reflect=True)
Base = declarative_base()
qa = Blueprint('qa', __name__)

MAX_TICKET = 5
MINI_TICKET = 0
QUESTION_COST = 1
FIRST_TICKET = 2
FIRST_INTERN_TICKET = 2
FIRST_EMPLOYEE_TICKET = 3

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = 'slack_question'
    id = Column(String(100), primary_key=True)
    username = Column(String(100), index=True, unique=True)
    count = Column(Integer)
    attendance = Column(Integer, nullable=False)
    is_intern = Column(Integer, nullable=True)
    nickname = Column(String(100), primary_key=True)

    def __repr__(self):
        return '<User username={username} count={count}>'.format(username=self.username, count=self.count)


@qa.route('/question', methods=["POST"])
def question():
    session = Session()
    qa_ticket_username_list = [name for name, in session.query(User.username)]
    qa_ticket_nickname_list = [nickname for nickname, in session.query(User.nickname)]
    post_name = request.form['text'].strip("@")
    if post_name[-1:] in " ":
        post_name = post_name.strip(" ")
    if post_name in qa_ticket_username_list or qa_ticket_nickname_list:
        filtered_name_record = session.query(User).filter(
            or_(User.username == post_name, User.nickname == post_name)).first()
        if MINI_TICKET < filtered_name_record.count <= MAX_TICKET:
            filtered_name_record.count -= QUESTION_COST
            qa_info(filtered_name_record)
            session.commit()
            session.close()
            return ""
        else:
            session.close()
            return '質問回数が不足してます！'
    else:
        session.close()
        return "出勤を記録してください！"


def qa_info(filtered_name_record):
    qa_info_json = json.dumps({
        "text": "{username}さんは質問しました。残りの質問回数は{count}回です".format(username=filtered_name_record.nickname,
                                                                count=filtered_name_record.count)
    })
    requests.post(WEB_HOOK_URL, qa_info_json)


@qa.route('/create', methods=['POST'])
def create():
    session = Session()
    qa_ticket_username_list = [name for name, in session.query(User.username)]

    if request.form["text"] == "emp":
        new_username = User(id=request.form["user_id"], username=request.form["user_name"], count=FIRST_TICKET,
                            attendance=False, is_intern=False)
        return create_user(new_username, session)
    elif not request.form["user_name"] in qa_ticket_username_list:
        new_username = User(id=request.form["user_id"], username=request.form["user_name"], count=FIRST_TICKET,
                            attendance=False, is_intern=True)
        return create_user(new_username, session)
    else:
        session.close()
        return "もうメンバーですよ！"


def create_user(new_name, session):
    session.add(new_name)
    session.commit()
    session.close()
    return request.form["user_name"] + "さんを登録しました！"


@qa.route('/attendance', methods=['POST'])
def attendance():
    session = Session()
    qa_ticket_username_list = [name for name, in session.query(User.username)]
    post = request.form
    post_name = post["user_name"]
    attendance_id = post["user_id"]
    filtered_name_record = session.query(User).filter(User.username == post_name).first()
    if filtered_name_record.attendance == True:
        return "出勤済みです"
    elif post_name in qa_ticket_username_list:
        filtered_name_record.attendance = True
        filtered_name_time = WorkTime(user_id=attendance_id, username=post_name,
                                      attendance_time=datetime.datetime.now())
        session.add(filtered_name_time)

        if filtered_name_record.is_intern == True:
            filtered_name_record.count = FIRST_INTERN_TICKET
        else:
            filtered_name_record.count = FIRST_EMPLOYEE_TICKET
        attendance_infomation(filtered_name_record)
        session.commit()
        session.close()

        return post_name + "さんが出勤を記録しました！"

    else:
        session.close()
        return "メンバー登録してください！"


def attendance_infomation(filtered_name_record):
    attendance_info_json = json.dumps({
        "text": "{username}さんが出勤しました".format(username=filtered_name_record.nickname)
    })
    requests.post(WEB_HOOK_URL, attendance_info_json)


@qa.route('/leaving_work', methods=['POST'])
def leave():
    session = Session()
    qa_ticket_username_list = [name for name, in session.query(User.username)]
    post = request.form
    post_name = post["user_name"]

    if post_name in qa_ticket_username_list:
        leaving_work_record = session.query(User).filter(User.username == post_name).first()
        leaving_work_record.attendance = False
        leaving_time_order_record = session.query(WorkTime).filter(WorkTime.username == post_name).order_by(
            desc(WorkTime.id)).first()

        leaving_time_order_record.finish_time = datetime.datetime.now()
        leaving_infomation(leaving_work_record)
        session.commit()
        session.close()
        return post_name + "さん,今日もお疲れ様でした!"
    else:
        session.close()
        return "出勤した記録がないですよ！"


def leaving_infomation(leaving_work_record):
    leaving_work_info_json = json.dumps({
        "text": "{username}さんが退勤しました".format(username=leaving_work_record.nickname)
    })
    requests.post(WEB_HOOK_URL, leaving_work_info_json)


HOURLY_TICKET_ADDITION = 2


@qa.route("/counter")
def add_question():
    session = Session()
    add_question_user_record = session.query(User).filter(User.is_intern == True, User.attendance).all()

    for row in add_question_user_record:
        if row.count < 4:
            row.count += HOURLY_TICKET_ADDITION
        else:
            row.count = MAX_TICKET

    session.commit()
    session.close()
    return "Success"


@qa.route("/info", methods=['POST'])
def attendance_info():
    session = Session()
    attendance_user_list = [name for name, in session.query(User.nickname).filter(User.attendance == True).all()]
    info_user_name_str = "さんと".join(attendance_user_list)

    return info_user_name_str + "が出勤しています"
