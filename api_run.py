from fileinput import filename
import os
import requests
from flask import Flask, request, jsonify
import subprocess
import threading
import io
import shutil
import boto3
import uuid
import json


secret_file = os.path.join('secret.json')  # secrets.json 파일 위치를 명시

with open(secret_file) as f:
    secrets = json.loads(f.read())

def get_secret(setting):
    """비밀 변수를 가져오거나 명시적 예외를 반환한다."""
    try:
        return secrets[setting]
    except KeyError:
        error_msg = "Set the {} environment variable".format(setting)
        

# AWS credentials
aws_access_key_id = get_secret("aws_access_key_id")
aws_secret_access_key = get_secret("aws_secret_access_key")
region_name = get_secret("region_name")


# S3 bucket and key (path to file)
# bucket_name = '<your-bucket-name>'
# key = '<path/to/your/file.py>'
# file_path = '<local/path/to/your/file.py>'

# Create an S3 client
s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=region_name)

def s3_upload(file_path,bucket_name,key):
    # Upload the file to S3
    s3.upload_file(file_path, bucket_name, key)

    # Get the S3 URL
    return "https://{}.s3.amazonaws.com/{}".format(bucket_name, key)

class RemoteFile:

    def __init__(self, url):
        self.url = url
        self.filename = self.get_filename_from_url(url)
        self._data_stream = None

    @staticmethod
    def get_filename_from_url(url):
        return url.split('/')[-1]

    @property
    def data_stream(self):
        if self._data_stream is None:
            response = requests.get(self.url, stream=True)
            if response.status_code == 200:
                self._data_stream = io.BytesIO(response.content)
            else:
                raise Exception(f"Error downloading file from URL: {self.url}, status code: {response.status_code}")
        return self._data_stream

    def read(self, *args, **kwargs):
        return self.data_stream.read(*args, **kwargs)



app = Flask(__name__)

def save_voice_data(file, output_folder):
    try:
        filename = os.path.join(output_folder, file.filename)
        with open(filename, 'wb') as f:
            f.write(file.read())
        print(f"Saved: {filename}")
        return True
    except Exception as e:
        print(f"Error: {e}")
    return False

def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"오류 발생 - 종료 코드: {result.returncode}\n오류 메시지: {result.stderr.strip()}"
    except Exception as e:
        return f"오류 발생: {e}"

# 이 함수는 전송한 후 디렉터리와 파일을 삭제합니다.
def clean_up_directory(directory):
    shutil.rmtree(directory)

def delete_specific_file(file_path):
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
            print(f"{file_path} 파일이 삭제되었습니다.")
        except OSError as e:
            print(f"파일 삭제 중 에러 발생: {e}")
    else:
        print(f"{file_path} 파일을 찾을 수 없습니다.")


def handle_request(voice_files,singer_voice_file,user_seq,ai_cover_id):
    voice_folder = 'preprocess'
    vocal_folder = 'exp'

    singer_voice_file.filename = 'vocal.wav'
    save_voice_data(singer_voice_file, vocal_folder)

    #save_voice_data(voice_files, voice_folder)
    #success_voice_files = []
    a=1
    for voice_file in voice_files:
        voice_file.filename=str(a)+'.wav'
        a+=1
        save_voice_data(voice_file, voice_folder)
        #success_voice_files.append(success)

    command_list = [
        "python sep_wav.py",
        "python draw.py",
        "python preprocess.py -c configs/combsub.yaml",
        "python train.py -c configs/combsub.yaml",
        'python main.py -i "exp\\vocal.wav" -m "exp\\combsub-test\\model_best.pt" -o "exp\\vocal_trans.wav" -k 0 -id 1 -eak 0'
    ]

    results = []

    for command in command_list:
        result = execute_command(command)
        results.append(result)

    for idx, result in enumerate(results):
        print(f"Command {idx+1} 실행 결과:\n{result}\n")

    # S3 bucket and key (path to file)
    # bucket_name = '<your-bucket-name>'
    # key = '<path/to/your/file.py>'
    # file_path = '<local/path/to/your/file.py>'

    # 합성한 음성 파일
    f_name = uuid.uuid3(uuid.NAMESPACE_URL,str(user_seq))
    AI_sing = s3_upload('exp/vocal_trans.wav', 'ssarout', f'ai-cover/{f_name}'+'.wav')
    
    # 학습 데이터
    f_name = uuid.uuid3(uuid.NAMESPACE_URL,str(ai_cover_id))
    AI_model = s3_upload('exp/combsub-test/model_best.pt','ssarout',f'model/{f_name}'+'.pt') #파일 이름


    # 반환 후 디렉터리를 정리
    clean_up_directory('data')
    clean_up_directory('preprocess')
    delete_specific_file('exp/vocal.wav')
    # delete_specific_file('exp/vocal_trans.wav')
    delete_specific_file('exp/combsub-test/log_info.txt')
    delete_specific_file('exp/combsub-test/model_best.pt')
    clean_up_directory('exp/combsub-test/logs')


    #처리 후 json put 요청
    url = "http://192.168.30.201:8080/api/v1/ai/covers"

    data = {
        "userSeq": "1",
        "aiCoverId": ai_cover_id,
        "aiCoverFile": AI_sing,
        "modelFile": AI_model
    }

    response = requests.put(url, json=data)
    print(response)


@app.route('/process_audio', methods=['POST'])
def process_audio():
    data = request.json
    os.makedirs('data', exist_ok=True)
    os.makedirs('preprocess', exist_ok=True)
    if 'userSeq' in data and 'aiCoverId' in data and 'voiceFileUrlList' in data and 'singerVoiceFileUrl' in data:
        user_seq = data['userSeq']
        ai_cover_id = data['aiCoverId']
        voice_file_url_list = data['voiceFileUrlList']
        singer_voice_file_url = data['singerVoiceFileUrl']

        voice_files = [RemoteFile(url) for url in voice_file_url_list]
        singer_voice_file = RemoteFile(singer_voice_file_url)

        t = threading.Thread(target=handle_request, args=(voice_files,singer_voice_file,user_seq,ai_cover_id))
        t.start()

        return jsonify({"message": "Audio data downloaded and processing started."}), 200
    else:
        return jsonify({"error": "Invalid request. 'voiceFileUrlList' and 'singerVoiceFileUrl' parameters are required."}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

