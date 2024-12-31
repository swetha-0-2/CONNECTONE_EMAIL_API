import requests
import json
import time
import base64
import os
import pymysql
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from robot.api.deco import keyword

db_host = '10.20.50.85'
db_user = 'qauser'
db_pass = 'Test123'
db_name = 'CON_DB'
db_port = 3306
attachment_folder_path = "C:/Users/SwethaV/Desktop/CONNECTONE_EMAIL_API/attachements"

def get_32_byte_key(key):
    return hashlib.sha256(key.encode()).digest()

def encrypt_text(text, key):
    key = get_32_byte_key(key)
    iv = key[:16]  
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_text = cipher.encrypt(pad(text.encode(), AES.block_size))  
    return base64.b64encode(encrypted_text).decode('utf-8')  

def convert_file_to_base64(file_path):
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode('utf-8')

def connect_to_db():
    try:
        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_pass,
            database=db_name,
            port=db_port
        )
        print("Database connection established.")
        return connection
    except pymysql.MySQLError as e:
        print(f"Error connecting to database: {e}")
        return None

def check_message_id_in_db(connection, message_id):
    with connection.cursor() as cursor:
        query = "SELECT * FROM email_attempt_log WHERE uniqueid = %s"
        cursor.execute(query, (message_id,))
        result = cursor.fetchone()
        print(f"Checked for messageId {message_id} in email_attempt_log: {'Found' if result else 'Not Found'}")  
        return result is not None, result[27] if result else None

def check_mid_in_dlr_log(connection, mid):
    with connection.cursor() as cursor:
        query = "SELECT * FROM email_dlr_log WHERE mid = %s"
        print(f"Executing query: {query} with MID = {mid}")  
        cursor.execute(query, (mid,))
        result = cursor.fetchone()
        if result:
            print(f"MID {mid} found in email_dlr_log.")  
        else:
            print(f"MID {mid} NOT found in email_dlr_log.")  
        return result is not None

def update_payload_with_attachments(payload, attachment_folder_path):
    attachment_details = payload['message']['attachments']['attachmentDetails']
    for attachment in attachment_details:
        file_name = attachment['name']
        file_path = os.path.join(attachment_folder_path, file_name)
        attachment['attachmentData'] = convert_file_to_base64(file_path) if os.path.exists(file_path) else ""
    return payload

def encrypt_payload_fields(payload, encryption_key):
    for field in ['bcc', 'cc', 'recipients', 'body']:
        if field in payload['message']:
            field_value = payload['message'][field]
            if isinstance(field_value, list):
                field_value = ','.join(field_value)  
            payload['message'][field] = encrypt_text(field_value, encryption_key)
    return payload

def send_post_request(url, payload):
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    print(f"Sent POST request to {url} with response status: {response.status_code}") 
    if response.status_code == 200:
        return response.json()
    return None

def get_mid_response(mid):
    mid_url = f"http://10.20.51.52/ConnectOneUrl/edlr/edlr?msgid={mid}&from=alerts@page247.net&to=swetha.v@karix.com&stime=2024-12-24 11:40:38&dtime=2024-12-24 11:40:39&status=001&reason=delivered&provider=karixEmail&err=0"
    
    print(f"Hitting MID URL: {mid_url}")
    
    try:
        print(f"Sending GET request to MID URL: {mid_url}")  
        response = requests.get(mid_url)
        if response.status_code == 200:
            print(f"Successfully received response for MID {mid}: {response.json()}")
            return response.json()  
        else:
            print(f"Failed to receive response for MID {mid}. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error while sending GET request for MID {mid}: {e}")
    return None

def validate_mid(connection, mid):
    print(f"Validating MID: {mid}")
    
    mid_response = get_mid_response(mid)
    if not mid_response:
        print(f"Failed to get response from MID URL for MID {mid}.")
        return "Fail"

    print("Waiting for the DLR log to be updated...")
    time.sleep(10)  

    if check_mid_in_dlr_log(connection, mid):
        print(f"Valid MID found. MID {mid} validation successful.")
        return "Pass"
    else:
        print(f"MID {mid} not found in email_dlr_log. Validation failed.")
    return "Fail"

def execute_test_case(test_desc, test_case_id, url, payload, expected_response):
    if not payload:
        print("No Payload provided. Test case failed.")  
        return "Fail (No Payload)"

    try:
        payload_json = json.loads(payload)
        expected_response_json = json.loads(expected_response)

        encryption_key = "qwertyuiopasdfghjklzxcvbnmqwerty"
        payload_with_encryption = encrypt_payload_fields(payload_json, encryption_key)

        payload_with_attachments = update_payload_with_attachments(payload_with_encryption, attachment_folder_path)

        actual_response = send_post_request(url, payload_with_attachments)
        if not actual_response:
            print("API request failed. Test case failed.") 
            return "Fail"

        message_id = actual_response.get('messageId', '')
        print(f"Fetched messageId: {message_id}")

        if actual_response.get("requestStatus", "").lower() == "failed":
            print(f"Request failed with status: {actual_response.get('requestStatus')}")  
            print(f"Expected Response: {json.dumps(expected_response_json, indent=4)}")
            print(f"Actual Response: {json.dumps(actual_response, indent=4)}")
            return "Pass" if actual_response == expected_response_json else "Fail"
        
        if message_id:
            expected_response_json['messageId'] = message_id
            print(f"Expected response after adding messageId: {expected_response_json}")  

            if actual_response == expected_response_json:
                time.sleep(10) 

                connection = connect_to_db()
                if connection:
                    found, mid = check_message_id_in_db(connection, message_id)
                    if found:
                        print(f"messageId {message_id} found in database, MID: {mid}")
                        validation_result = validate_mid(connection, mid) 
                        if validation_result == "Pass":
                            connection.close()
                            return "Pass"
                        else:
                            print(f"Mid validation failed for MID {mid}.")
                    else:
                        print(f"messageId {message_id} not found in database. Test case failed.")  
                    connection.close()
                else:
                    print("Database connection failed. Test case failed.")  

                return "Fail"
        return "Fail"

    except Exception as e:
        print(f"Error during test case execution: {e}")  
        return "Fail"

@keyword
def execute_api(test_case_id, test_desc, url, payload, expected_response):
    return execute_test_case(test_desc, test_case_id, url, payload, expected_response)
