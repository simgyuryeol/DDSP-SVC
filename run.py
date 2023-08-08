import subprocess
import os

def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"오류 발생 - 종료 코드: {result.returncode}\n오류 메시지: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "오류 발생 - 실행 시간이 1시간을 초과하였습니다."
    except Exception as e:
        return f"오류 발생: {e}"

# def delete_file(file_path):
#     try:
#         if os.path.exists(file_path):
#             os.remove(file_path)
#             print(f"파일 '{file_path}'가 삭제되었습니다.")
#         else:
#             print(f"파일 '{file_path}'가 존재하지 않습니다.")
#     except OSError as e:
#         print(f"파일 삭제 오류: {e}")

# 해당 명령어들 실행
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

# result = execute_command("python sep_wav.py")
# results.append(result)

# result = execute_command("python draw.py")
# results.append(result)

# result = execute_command("python preprocess.py -c configs/combsub.yaml")
# results.append(result)

# result = execute_command("python train.py -c configs/combsub.yaml")
# results.append(result)

# result = execute_command('python main.py -i "exp\\vocal.wav" -m "exp\\combsub-test\\model_best.pt" -o "exp\\vocal_trans.wav" -k 0 -id 1 -eak 0')
# results.append(result)

# 결과 출력
for idx, result in enumerate(results):
    print(f"Command {idx+1} 실행 결과:\n{result}\n")

# 결과물 파일 삭제
# output_file_path = "C:\\DDSP-SVC\\exp\\vocal_trans.wav"
# delete_file(output_file_path)