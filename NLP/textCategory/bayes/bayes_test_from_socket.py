# -*- coding:utf-8 -*-

import os
import time
import json
import random
import socket
import configparser
import traceback
import itertools
import pika
from sklearn.externals import joblib
from bayes.bayes_train import get_words, bernousNB_save_path, isChat
from Logger import *

'''
    从文件读取模型并进行分类，打开socket，接收消息
'''

logfile = 'D:/data/bayes_from_socket.log'
log = Logger(logfile, level='info')

AnswerDict = []
intentionList = []

def loadAnswers():
    with open("../kdata/intention_answer.txt", encoding="utf-8", errors="ignore") as fo:
        for line in fo.readlines():
            arr = line.strip().split("\t")
            AnswerDict[arr[0]] = arr[2]
            intentionList.append(arr[0])
    print("load answers finished")

def getAnswer(intention):
    result_list = AnswerDict[intention].split("|")
    return result_list[random.randint(0, len(result_list) - 1)]

'''
    获取最新的模型
'''
def get_newest_model(model_path):
    model_full_path = os.path.join(os.path.dirname(__file__), model_path)
    model_full_path = model_full_path.replace('\\', '').replace('.', '')

    if os.path.exists(model_full_path):
        # 按文件最后修改时间排序，reverse=True表示降序排序
        filelist = sorted(os.listdir(model_full_path), key=lambda x: os.path.getctime(os.path.join(model_full_path, x)), reverse=True)
        log.logger.info(("Use Model: %s" % (os.path.join(model_full_path, filelist[0]))))
        return os.path.join(model_full_path, filelist[0])
    else:
        log.logger("Model path is not exists")

'''
    读取配置文件，获取打开SocketServer的ip和端口
'''
def getSocketConfig():
    cf = configparser.ConfigParser()
    cf.read("../kdata/config.conf")
    host = str(cf.get("sserver", "host"))
    port = int(cf.get("sserver", "port"))
    return host, port

'''
    获取rabbitmq连接
    :param nodeName 指定配置文件的哪个节点
'''
def getRabbitConn(nodeName):
    cf = configparser.ConfigParser()
    cf.read("../kdata/config.conf")
    host = str(cf.get(nodeName, "host"))
    port = int(cf.get(nodeName, "port"))
    username = str(cf.get(nodeName, "username"))
    password = str(cf.get(nodeName, "password"))
    EXCHANGE_NAME = str(cf.get(nodeName, "EXCHANGE_NAME"))
    vhost = str(cf.get(nodeName, "vhost"))
    routingKey = str(cf.get(nodeName, "routingKey"))

    credentials = pika.PlainCredentials(username=username, password=password)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port, virtual_host=vhost, credentials=credentials))
    channel = connection.channel()
    # channel.queue_declare(queue=routingKey, durable=True)    # 定义持久化队列
    # channel.queue_declare(queue=routingKey)  # 定义持久化队列

    return channel, EXCHANGE_NAME, routingKey

'''
    测试多项式分类器
'''
def test_bayes(model_file):
    clf = joblib.load(model_file)
    # loadAnswers()    # 加载 意图-答案 表
    backstage_channel, backstage_EXCHANGE_NAME, backstage_routingKey = getRabbitConn("rabbit2backstage")
    log.logger.info("rabbit2backstage producer 已启动：%s %s %s" % (backstage_channel, backstage_EXCHANGE_NAME, backstage_routingKey))
    print("rabbit2backstage producer 已启动：%s %s %s" % (backstage_channel, backstage_EXCHANGE_NAME, backstage_routingKey))

    portrait_channel, portrait_EXCHANGE_NAME, portrait_routingKey = getRabbitConn("rabbit2portrait")
    log.logger.info("rabbit2portrait producer 已启动：%s %s %s" % (portrait_channel, portrait_EXCHANGE_NAME, portrait_routingKey))
    print("rabbit2portrait producer 已启动：%s %s %s" % (portrait_channel, portrait_EXCHANGE_NAME, portrait_routingKey))

    sev = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP连接
    HOST, PORT = getSocketConfig()
    sev.bind((HOST, PORT))    # 192.168.120.133是连安卓时用
    sev.listen()
    log.logger.info("语义识别端已启动。。。")
    print("语义识别端已启动。。。")

    conn, addr = sev.accept()
    log.logger.info("%s %s" % (conn, addr))
    print(conn, addr)
    log.logger.info((conn, addr))
    sentences = ""
    empty_package_nums = 0    # 记录空包的数量

    while True:
        try:
            recvStr = bytes.decode(conn.recv(4096), encoding='utf-8')
            if len(recvStr) == 0:    # 如果是安卓客户端，当客户端断开时，服务端收到的是空包
                empty_package_nums +=1
                if empty_package_nums >= 20000:
                    raise ConnectionResetError
                continue
            else:
                empty_package_nums = 0    # 如果遇到非空包来，则空包数量重新计数

            recvJson = json.loads(recvStr)
            log.logger.info(recvJson)
            daotaiID = recvJson["daotaiID"]
            sentences = recvJson["message"]
            timestamp = recvJson["timestamp"]
        except ConnectionResetError as connectionResetError:
            log.logger.warn("客户端已断开，正在等待重连: ", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            print("客户端已断开，正在等待重连: ", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            conn, addr = sev.accept()
            log.logger.info("%s %s" % (conn, addr))
            print(conn, addr)
            log.logger.info((conn, addr))
        except Exception as e:
            traceback.print_exc(file=open(logfile, 'a+'))
            continue

        word_list = []
        new_sentences = get_words(sentences)
        if isChat(new_sentences) is False:  # 如果不是闲聊
            word_list.append(new_sentences)
            predict = clf.predict(word_list)
            for left in predict:
                if left == "坐车":
                    left = "坐高铁"
                # answer = getAnswer(left)
                # thread.start_new_thread(send_msg, ())    # 新开一个线程，通知前端
                print(left, "-->", word_list, "-->", sentences)
                log.logger.info((left, "-->", word_list, "-->", sentences))

                yuyiDict = {}
                yuyiDict["daotaiID"] = daotaiID
                yuyiDict["sentences"] = sentences
                yuyiDict["timestamp"] = timestamp
                yuyiDict["intention"] = left    # 意图

                # 之后将yuyiDict写入到消息队列
                # channel.basic_publish(exchange=EXCHANGE_NAME,
                #                       routing_key=routingKey,
                #                       body=str(yuyiDict),
                #                       properties=pika.BasicProperties(    # 如果仅仅是设置了队列的持久化，仅队列本身可以在rabbit-server宕机后保留，队列中的信息依然会丢失，如果想让队列中的信息或者任务保留，还需要这行代码
                #                           delivery_mode=2,  # 使消息或任务也持久化存储
                #                       ))
                backstage_channel.basic_publish(exchange=backstage_EXCHANGE_NAME,
                                                routing_key=backstage_routingKey,
                                                body=str(yuyiDict))    # 将语义识别结果给到后端

                # 人物画像端
                portraitDict = {}    # 人物画像要填的字段
                portraitDict["source"] = "yuyi"    # 标识来源是语义yuyi端还是backstage后端
                portraitDict["timestamp"] = timestamp
                portraitDict["daotaiID"] = daotaiID
                portraitDict["portrait"] = None    # 画像部分留空
                portraitDict["savefile"] = ""      # 图片保存路径
                portraitDict["sentences"] = sentences    # 询问问题
                portraitDict["timestamp"] = timestamp    # 意图
                portrait_channel.basic_publish(exchange=portrait_EXCHANGE_NAME,
                                               routing_key=portrait_routingKey,
                                               body=str(portraitDict))
        else:
            print("咨询类", "-->", sentences)  # 闲聊场景，将原话传给闲聊机器人
            log.logger.info(("咨询类", "-->", sentences))


def main():
    # test_bayes(get_newest_model(multinamialNB_save_path))
    test_bayes(get_newest_model(bernousNB_save_path))
    # print(get_newest_model(multinamialNB_save_path))
    # print(get_newest_model(bernousNB_save_path))
    # divideTestSet(test_set)

    # model_file = "D:/workspace/Pycharm_Projects/develop-python-case/NLP/textCategory/bayes/model/bernousNB/bernousNB_1576579523_9512195121951219_0_0.m"
    # test_bayes(model_file)

if __name__ == '__main__':
    main()