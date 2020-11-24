import json
import boto3
import time
import logging
from boto3.dynamodb.conditions import Key, Attr
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


dynamodb = boto3.resource('dynamodb')
table_p = dynamodb.Table('pwd')
table_v = dynamodb.Table('visitor_ex_img')


def lambda_handler(event, context):
    logger.debug("lambda0 for visitor start")
    passcode = get_passcode_from_request(event)
    
    if passcode is None:
        return give_failure_response_body("sorry,we don't get your OPT, please input again")
    ex_img_name = find_visitor(passcode)
    if ex_img_name is None:
        return give_failure_response_body("sorry,this is a wrong OPT, please input again")
    visitor = get_visitor_info(ex_img_name)
    if visitor is None:
        return give_failure_response_body("sorry,you are not allowed to get in by owner, permission dennied")
    else:
        return give_success_response_body(visitor)
    
    
    

def get_passcode_from_request(event):
    
    body = event
    if "messages" not in body:
        logger.error("body type error")
        return None
    messages = event["messages"]
    if not isinstance(messages,list) or len(messages) < 1:
        logger.error("messages type error or no message")
        return None
    message = messages[0]
    if "unconstructed" not in message:
        logger.error("message missing unconstructed")
        return None
    if "passcode" not in message["unconstructed"]: 
        logger.error("message missing passcode")
        return None
    passcode = message["unconstructed"]["passcode"]
    return passcode

def find_visitor(passcode):
    response = table_p.get_item(Key={"passcode": passcode})
    
    
    
    if "Item" not in response:
        return None
        
        
    expire_time = int(time.time())
    
    if expire_time > response['Item']['expirationTime']:
        print("aaaaaaaaaaaaaaaaaaaaaa")
        print (response['Item']['expirationTime'])
        print("aaaaaaaaaaaaaaaaaaaaaa")
        print(expire_time)
        return None
    
    ex_img_name = response['Item']['ex_img_name']
    # print("hahahahahha:",faceId)
    return ex_img_name
    
def get_visitor_info(ex_img_name):
    responce = table_v.get_item(Key={"ex_img_name": ex_img_name})
    if "Item" not in responce:
        return None
    visitor = responce["Item"]
    return visitor
    
def give_success_response_body(visitor):
    text = ""
    body = {
        "messages":[
            {
                "type":"success response",
                "unconstructed":{
                    "valid": True,
                    "visitor_info":visitor,
                    "text": text,
                    "time":time.time()
                }
            }]
    }
    
    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin" : "*"
        },
        'body': body
    }

def give_failure_response_body(text):
    
    body = {
        "messages":[
            {
                "type":"failure response",
                "unconstructed":{
                    "valid": False,
                    "vaistor_info": None,
                    "text": text,
                    "time":time.time()
                }
            }]
    }
    
    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin" : "*"
        },
        'body': body
    }