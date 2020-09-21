# coding:utf-8

from . import api
from ihome.utils.captcha.captcha import captcha
from ihome import redis_store, constants
from flask import current_app, jsonify, make_response, request
from ihome.utils.response_code import RET
from ihome.models import User
from ihome.libs.yuntongxun.sms import CCP

import random

# GET 127.0.0.1/api/v1.0/image_codes/<image_code_id>


@api.route("/image_codes/<image_code_id>")
def get_image_code(image_code_id):
    """获取图片验证码
    : params image_code_id: 图片验证码编号
    ：return :验证码图片
    """
    # 业务逻辑处理
    # 生成验证码图片
    # 名字，真实文本，图片数据
    name, text, image_data = captcha.generate_captcha()

    # 将验证码真实值与编导保存到redis中,设置有效期
    # redis的数据类型: 字符串 列表 哈希 set（集合）
    # 使用哈希维护有效期的时候只能整体设置
    # "image_codes": {"id1":"abc","id2":"123"} hset{"image_codes","id1","abc"}#设置值 hget("id1")#取值

    # 单条维护记录，选用字符串
    # "image_code_id1":"真实值"
    # redis_store.set("image_code_%s" % image_code_id, text)
    # redis_store.expire("image_code_%s" % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES)
    try:
        # 记录名字，有效期，记录文本
        redis_store.setex("image_code_%s" % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    except Exception as e:
        # 记录日志
        current_app.logger.error(e)
        # return jsonify(errno=RET.DBERR, errmsg="保存图片验证码失败")
        return jsonify(errno=RET.DBERR, errmsg="save image code id failed")

    # 返回图片
    resp = make_response(image_data)
    resp.headers["Content-Type"] = "image/jpg"
    return resp


# GET /api/v1.0/sms_code/<mobile>?image_code=xxx&image_code_id=xxx
@api.route("/sms_codes/<re(r'1[34578]\d{9}'):mobile>")
def get_sms_code(mobile):
    """获取短信验证码"""
    # 获取参数
    image_code = request.args.get("image_code")
    image_code_id = request.args.get("image_code_id")

    # 校验参数
    if not all([image_code, image_code_id]):
        # 表示参数不完整
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")

    # 业务逻辑处理
    # 从redis中取出真实的图片验证码
    try:
        real_image_code = redis_store.get("image_code_%s" % image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="redis数据库异常")

    # 判断图片验证码是否过期
    if real_image_code is None:
        # 表示图片验证码没有或者过期
        return jsonify(errno=RET.NODATA, errmsg="图片验证失败")

    # 删除redis中的图片验证码，防止用户使用同一个图片验证码验证多次
    try:
        redis_store.delete("image_code_%d" % image_code_id)
    except Exception as e:
        current_app.logger.error(e)

    # 与用户输入的值对比
    if image_code.lower() != real_image_code.lower():
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")

    # 判断对于这个手机号的操作，在60s内有没有之前的记录，如果有，则认为用户重复操作
    try:
        send_flag = redis_store.get("send_sms_code_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if send_flag is not None:
            # 表示在60s内之前有重复操作
            return jsonify(errno=RET.REQERR, errmsg="请求重复")

    # 判断手机是否存在
    # 从数据库中的查询手机号是否存在
    try:
        obj = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
    else:
        if obj is not None:
            # 表示手机号已存在
            return jsonify(errno=RET.DATAEXIST,errmsg="号码已存在")

    # 如果手机号不存在，则生成短信验证码
    sms_code = "%06d" % random.randint(0,999999)

    # 将短信验证码保存到redis中
    try:
        # 记录名字，有效期，记录文本
        redis_store.setex("sms_code_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # 保存发送给这个手机号的记录，防止用户在60s内再次发送短信
        redis_store.setex("send_sms_code_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
    except Exception as e:
        # 记录日志
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码异常")

    # 发送短信
    try:
        ccp = CCP()
        result = ccp.send_template_sms(mobile, [sms_code, int(constants.SMS_CODE_REDIS_EXPIRES/60)], 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="发送异常")

    # 返回值
    if result == 0:
        # 发送成功
        return jsonify(errno=RET.OK, errmsg="发送成功")
    else:
        return jsonify(errno=RET.THIRDERR, errmsg="发送失败")






















