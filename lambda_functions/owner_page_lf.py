import json
import boto3
import time
import logging
import random
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# validate OPT (10)
# retrieve visitor infomation (11)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --------------------------- setting information ---------------------------
dynamodb = boto3.resource('dynamodb')
pwd_table = dynamodb.Table('pwd')
vis_table = dynamodb.Table('visitor_ex_img')

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
bucket1='hw2-gate-known-faces-bucket2' 
bucket2 = 'hw2-face-storage' # unkown
sns = boto3.client("sns", region_name="us-west-2")
wp2_url_visitor = 'http://hw2-gate-door-visitors.s3-website-us-east-1.amazonaws.com'
rekognition=boto3.client('rekognition')
collection_id='visitors_copy' #region west-2


def lambda_handler(event, context):
    name, phone, img = get_info_from_owner_request(event)
    if None in [name,phone,img]:
        return give_failure_response_body("can not match new visitor")
    if phoneCheck(phone) is False:
        return give_failure_response_body("wrong phone number")
    img_name = save_known_img(img,name)
    faceId = add_faces_to_collection(img_name)
    if faceId is None:
        return give_failure_response_body("can not match new visitor")
    ex_img_name = store_visitor_record(faceId,name,phone,img_name)
    passcode = generate_passcode()
    store_passcode_record(passcode,ex_img_name)
    send_message(phone,passcode)
    delete_unknown_img(img)
    return give_success_response_body("new visitor updated, we have sent the passcode to the phone:{}".format(phone))

def phoneCheck(phone):
    phone = phone.replace('-', '')
    if len(phone) != 10:
        return False
    for i in phone:
        if not i.isalnum():
            return False
    return 

# ---------------------------  sending message to visitor   ------------------------
def send_message(phone,passcode):
    sns = boto3.client("sns", region_name="us-west-2")
    txt = "hi, your passcode is:" + str(passcode) + "\nPlease use this url to get into the door\n" + wp2_url_visitor
    sns.publish(
        PhoneNumber="+1 "+ str(phone),
        Message=txt
        )

# --------------------------- get INFO from owner   ------------------------
def get_info_from_owner_request(event):
    body = event
    if "messages" not in body:
        return None,None,None
    messages = event["messages"]
    if not isinstance(messages,list) or len(messages) < 1:
        logger.error("no message")
        return None,None,None
    message = messages[0]
    if "unconstructed" not in message:
        logger.error("message missing unconstructed")
        return None,None,None
    if "name" not in message["unconstructed"]: 
        logger.error("message missing name")
        return None,None,None
    if "phone" not in message["unconstructed"]: 
        logger.error("message missing phone")
        return None,None,None
    if "img" not in message["unconstructed"]: 
        logger.error("message missing img")
        return None,None,None
    name = message["unconstructed"]["name"]
    phone = message["unconstructed"]["phone"]
    img = message["unconstructed"]["img"]
    
    img = img.split('/')[-1]
    return name, phone, img

# --------------------------- save visitor img to bucket1 ------------------------
# bucket1='hw2-gate-known-faces-bucket' #known-face
# bucket2 = 'hw2-face-storage' # unkown-face
# img: unknown.jpg
def save_known_img(img,name):
    img_str = name + ".jpg"
    
    s3_client.download_file(bucket2, img, '/tmp/visitor.jpg') # 类似于一个中转站吗 user上传到bucket2然后下载到bukect1成为用户之后删掉bckt2中的暂存
    try:
        response = s3_client.upload_file('/tmp/visitor.jpg', bucket1, img_str, ExtraArgs={'ACL':'public-read'})
    except ClientError as e:
        logging.error(e)
  
    return img_str
# --------------------------- delete tmp unknown img ------------------------
def delete_unknown_img(img):
    s3.Object(bucket2, img).delete()
    
# --------------------------- add face to collection ------------------------
def add_faces_to_collection(photo):
    
    response=rekognition.index_faces(CollectionId=collection_id,
                                Image={'S3Object':{'Bucket':bucket1,'Name':photo}},
                                ExternalImageId=photo,
                                MaxFaces=1,
                                QualityFilter="AUTO",
                                DetectionAttributes=['ALL'])

    #face["Face"]['ExternalImageId']                       
    for faceRecord in response['FaceRecords']:
         print('  Face ID is : ' + faceRecord['Face']['FaceId'] + '  Location: {}'.format(faceRecord['Face']['BoundingBox']))
    
    faceId = response['FaceRecords'][0]['Face']['FaceId']
    
    return faceId
 
# --------------------------- store visitor info in DB2 ------------------------   
#store_visitor_record(faceId,name,phone,img_name)
def store_visitor_record(faceId,name,phone,img_str):
    named_tuple = time.localtime() 
    time_string = time.strftime("%m-%d-%YT%H:%M:%S", named_tuple)
    vis_table.put_item(
        Item={
            "ex_img_name": name + '.jpg',
            "faceID": faceId,
            "name": name,
            "phoneNumber": phone,
            "photos": [
                {
                 "bucket": bucket1,
                 "createdTimeStamp": time_string,
                 "objectKey": img_str
                }
            ]
        }
    )
    ex_img_name = name + '.jpg'
    print("in store_visitor_record, the ex_img_name is:", ex_img_name)
    return ex_img_name
# --------------------------- generate OTP ------------------------
def generate_passcode():
    PIN = ""
    for i in range(6):
        PIN = PIN + str(random.randint(0,9))
    passcode = PIN
    return passcode

# --------------------------- store OTP into DB1 ------------------------
def store_passcode_record(passcode,ex_img_name):
    expiration_time = int(time.time() + 300)
    # print(type(expiration_time))
    pwd_table.put_item(
        Item={
            "passcode":passcode,
            "ex_img_name": ex_img_name,
            "expirationTime": expiration_time
        }
    )


# --------------------------- success response  ------------------------
def give_success_response_body(visitor):
    text = ""
    body = {
        "messages":[
            {
                "type":"successresponce",
                "unconstructed":{
                    "valid": True,
                    "text": text,
                    "time":time.time()
                }
            }]
    }
    
    return {
        'statusCode': 200,
        'headers' : {
            "Access-Control-Allow-Origin" : "*"
        },
        'body': body
    }

# --------------------------- failure response if not found visitor or phone# error ------------------------
def give_failure_response_body(text):
    
    body = {
        "messages":[
            {
                "type":"failure responce",
                "unconstructed":{
                    "valid": False,
                    "text": text,
                    "time":time.time()
                }
            }]
    }
    
    return {
        'statusCode': 200,
        'headers' : {
            "Access-Control-Allow-Origin" : "*"
        },
        'body': body
    }