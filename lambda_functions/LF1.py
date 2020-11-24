import time
import random
import logging
import base64
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import sys
sys.path.insert(1, '/opt')
import cv2
import json
import boto3
# --------------------------- lambda_handler ------------------------
def lambda_handler(event, context):
   
    kvd1_data = decoder_kvd1(event)
    print("raw event: ",event)
    print("kv1_data is:",kvd1_data )
    have_face, ex_img_name = get_face(kvd1_data)
    print("have_face, ex_img_name are:",have_face, ex_img_name)
    # exist, name, phone = exist_visitor(have_face,faceId)
    exist,name,phone = exist_visitor2(have_face,ex_img_name)
    print("phone is:",phone)
    if have_face:
        if exist:
            print("we found this guy in db")
            passcode = generate_passcode()
            store_passcode_record(passcode, ex_img_name)
            txt = sns_for_visitor(passcode, name)
            send_message(phone, txt)
        else:
            print("we did not find this guy in db")
            owner_phone = "9177039994"
            img_url = get_unknown_visitor_image()
            print (img_url)
            web_authorize_url = get_webpage_for_authorize(img_url)
            txt = sns_for_owner(web_authorize_url)
            send_phone(owner_phone, web_authorize_url)
            
            
# --------------------------- send_email ------------------------
def send_phone(owner_phone,web_authorize_url):
    # sns = boto3.client('sns',region_name='us-west-2')
    sns = boto3.client("sns", region_name="us-west-2")
    sns.publish(
        PhoneNumber="+1 "+owner_phone,
        Message="Hi, master. There is a visitor trying to visit you, please give the permission.\n" + web_authorize_url
    )


# --------------------------- generate sns text for owner ------------------------
def sns_for_owner(web_url):
    txt = "Hi, master. There is a visitor trying to visit you, please give the permission.\n" + web_url
    return txt        
# --------------------------- get_webpage_for_authorize ------------------------
def get_webpage_for_authorize(img_url):
    web_authorize_url = "http://hw2-gate-door-owners.s3-website-us-east-1.amazonaws.com"
    return web_authorize_url
            
# --------------------------- send ses message ------------------------
def send_message(phone, txt):
    print("this will send text msg")
    sns = boto3.client("sns", region_name="us-west-2")
    sns.publish(
        PhoneNumber="+1 "+phone,
        Message=txt
    )
# --------------------------- message for visitor  ------------------------           
def sns_for_visitor(passcode, name):
    web_url_for_visitor = "https://hw2-gate-door-visitors.s3.amazonaws.com/webpage2.html"
    txt = "Hi " + name + ", your passcode is:" + str(passcode) + "\nPlease use the following url to get into the door!\n" + web_url_for_visitor
    return txt
            
# --------------------------- store pwd  ------------------------
def store_passcode_record(passcode, ex_img_name):
    # expire after 5 minutes
    expire_time = int(time.time() + 300)
    print(type(expire_time))
    pwd_table.put_item(
        Item={
            "passcode": passcode,
            "ex_img_name": ex_img_name,
            "expirationTime": expire_time
        }
    )
# --------------------------- generate pwd ------------------------
def generate_passcode():
    # 6 bit PIN only contains number
    PIN = ""
    for i in range(6):
        PIN = PIN + str(random.randint(0,9))
    passcode = PIN
    return passcode
    
# --------------------------- check is visitor exists ------------------------
def exist_visitor2(have_face,ex_img_name):
    if not have_face or not ex_img_name:
        return False, None, None 
    response = vis_table.get_item(Key={"ex_img_name":ex_img_name})
    if "Item" not in response:
        return False, None, None
    visitor = response["Item"]
    print("Using external image name, found vistor ex_img_name is:",ex_img_name)
    return True, visitor["name"], visitor["phoneNumber"]
    
    
def exist_visitor(valid, faceId):
    if not valid:
        return False, None, None
    if faceId is None:
        return False, None, None
    response = vis_table.get_item(Key={"faceID": faceId})
    if "Item" not in response:
        return False, None, None
    visitor = response["Item"]
    print("found exist_visitor, visitor is,",visitor)
    return True, visitor["name"], visitor["phoneNumber"]
    

# --------------------------- decoder for kvd1 data ------------------------
def decoder_kvd1(event):
    code = event['Records'][0]['kinesis']['data']
    code_b = code.encode("UTF-8")
    data_b = base64.b64decode(code_b)
    data = data_b.decode("UTF-8")
    print (data)
    data = json.loads(data)
    return data
# --------------------------- get visiter's face from KVD1 ------------------------

def get_face(data):
    face_data = data["FaceSearchResponse"]
    if len(face_data) ==0:
        return False, None
    match_faces = face_data[0]["MatchedFaces"]
    if len(match_faces) == 0:
        return True, None
    face = match_faces[0]
    # faceId = face["Face"]["FaceId"]
    # return True, faceId
    external_img_name = face["Face"]['ExternalImageId']
    return True,external_img_name


# --------------------------- setting information ---------------------------
# For s3 buckets:
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
bucket = "hw2-face-storage"
# For Dynamodb: 
dynamodb = boto3.resource('dynamodb')
pwd_table = dynamodb.Table('pwd')
vis_table = dynamodb.Table('visitor_ex_img')

# --------------------------- function to get unknow visitor image from stream -------
def get_unknown_visitor_image():
    ### Kinesisvideo
    stream_ARN = "arn:aws:kinesisvideo:us-west-2:964570262610:stream/hw2videostream/1605307724203"

    kvs = boto3.client("kinesisvideo")

    response = kvs.get_data_endpoint(
        StreamARN = stream_ARN,
        APIName = 'GET_MEDIA'
    )

    endpoint_url = response['DataEndpoint']

    stream_client = boto3.client(
        'kinesis-video-media', 
        endpoint_url = endpoint_url, 
    )
    print(stream_client)

    kinesis_stream = stream_client.get_media(
        StreamARN=stream_ARN,
        # Identifies the fragment on the Kinesis video stream where you want to start getting the data from
        StartSelector={
            # Start with the latest chunk on the stream
            'StartSelectorType': 'NOW'
            }
    )
    print(kinesis_stream)
    # return "url"

    with open('/tmp/stream.mkv', 'wb') as f:
        streamBody = kinesis_stream['Payload'].read(512*512)
        f.write(streamBody)
       
        cap = cv2.VideoCapture('/tmp/stream.mkv')
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H','2','6','4'))
        ret, frame = cap.read() 
        cv2.imwrite('/tmp/frame.jpg', frame)
        img_name = "unknown.jpg" 
        s3_client.upload_file(
            '/tmp/frame.jpg',
            bucket, 
            img_name,
            ExtraArgs={'ACL':'public-read'}
        )
        cap.release()
    
    # print("image_name",img_name)
    img_url = "https://" + bucket + ".s3.amazonaws.com/" + img_name
    return img_url

