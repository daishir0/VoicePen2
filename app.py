from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
import os
import tempfile
import yaml
import ssl
from datetime import datetime
from pathlib import Path
import subprocess
from pydub import AudioSegment
import requests

app = Flask(__name__)

# Load configuration
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

# Initialize OpenAI client with API key from config
client = OpenAI(api_key=config['openai']['api_key'])

# データ保存用のディレクトリを作成
data_dir = Path('./data')
if not data_dir.exists():
    log("Data directory does not exist, creating it.")
    data_dir.mkdir(exist_ok=True)

def log(message):
    print(f"{datetime.now()} - {message}")

def convert_to_wav(input_file: str) -> str:
    log("convert_to_wav: Start")
    file_name, file_extension = os.path.splitext(input_file)
    wav_file = file_name + '.wav'
    
    if not os.path.exists(wav_file):
        log("convert_to_wav: Converting file")
        if file_extension.lower() in ['.mp3', '.m4a', '.mp4', '.webm']:
            try:
                subprocess.run(['ffmpeg', '-i', input_file, '-acodec', 'pcm_s16le', '-ar', '16000', wav_file], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                log(f"convert_to_wav: ffmpeg error: {e.stderr}")
                raise
        else:
            log("convert_to_wav: Unsupported file format")
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    log("convert_to_wav: End")
    return wav_file

def save_audio_and_text(audio_data: bytes, transcript: str) -> tuple[str, str]:
    """音声データとテキストを保存し、ファイルパスを返す"""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    audio_path = data_dir / f"{timestamp}.mp3"
    text_path = data_dir / f"{timestamp}.txt"
    
    # 一時的なwebmファイルを作成
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
        temp_audio.write(audio_data)
        temp_path = temp_audio.name

    try:
        # MP3に変換
        subprocess.run([
            'ffmpeg', '-i', temp_path,
            '-acodec', 'libmp3lame',
            str(audio_path)
        ], check=True, capture_output=True, text=True)
        
        # テキストを保存
        text_path.write_text(transcript, encoding='utf-8')
        
        log(f"Files saved: {audio_path}, {text_path}")
        return str(audio_path), str(text_path)
    finally:
        # 一時ファイルを削除
        os.unlink(temp_path)

@app.route('/')
def index():
    log("index: Rendering index.html")
    return render_template('index.html')

def handle_audio_data(audio_data):
    log("handle_audio_data: Start")
    log(f"Received audio data size: {len(audio_data)} bytes")
    try:
        # OpenAI APIを使用して音声を文字起こし
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name
            
            with open(temp_audio_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
        
        # 音声とテキストを保存
        audio_path, text_path = save_audio_and_text(audio_data, transcript.text)
        
        # 文字起こし結果をクライアントに送信
        # socketio.emit('transcription', {
        #     'text': transcript.text,
        #     'audio_path': audio_path,
        #     'text_path': text_path
        # })
    finally:
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
    log("handle_audio_data: End")

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio data provided'}), 400

    audio_file = request.files['audio_data']
    audio_data = audio_file.read()

    try:
        # 一時ファイルに保存してWhisper APIで文字起こし
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
            temp_audio.write(audio_data)
            temp_path = temp_audio.name
            
            with open(temp_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )

        # 音声とテキストを保存
        audio_path, text_path = save_audio_and_text(audio_data, transcript.text)
        
        return jsonify({
            'message': 'Audio processed successfully',
            'audio_path': audio_path,
            'text_path': text_path,
            'transcript': transcript.text
        }), 200

    except Exception as e:
        log(f"Error processing audio: {str(e)}")
        return jsonify({'error': 'Failed to process audio'}), 500

    finally:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)

@app.route('/upload_local_audio', methods=['POST'])
def upload_local_audio():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio data provided'}), 400

    audio_file = request.files['audio_data']
    audio_data = audio_file.read()

    # 一時ファイルに保存
    temp_audio_path = './temp_audio.webm'
    with open(temp_audio_path, 'wb') as temp_audio:
        temp_audio.write(audio_data)

    try:
        # 音声ファイルを30秒ごとに分割
        audio = AudioSegment.from_file(temp_audio_path)
        duration_ms = len(audio)
        chunk_duration_ms = 30 * 1000  # 30秒
        chunk_filepaths = []

        for start_time in range(0, duration_ms, chunk_duration_ms):
            end_time = min(start_time + chunk_duration_ms, duration_ms)
            chunk_audio = audio[start_time:end_time]
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            chunk_filepath = data_dir / f"{timestamp}.mp3"
            chunk_audio.export(chunk_filepath, format='mp3')
            chunk_filepaths.append(chunk_filepath)

            # Whisper APIで文字起こし
            with open(chunk_filepath, 'rb') as chunk_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=chunk_file
                )
            
            # テキストを保存
            text_filepath = data_dir / f"{timestamp}.txt"
            text_filepath.write_text(transcript.text, encoding='utf-8')

        return jsonify({
            'message': 'Audio processed successfully',
            'chunks': [str(filepath) for filepath in chunk_filepaths]
        }), 200

    except Exception as e:
        log(f"Error processing audio: {str(e)}")
        return jsonify({'error': 'Failed to process audio'}), 500

    finally:
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)

@app.route('/edit')
def edit():
    log("edit: Rendering edit.html")
    # ファイルの作成日時でソート
    text_files = sorted(list(data_dir.glob('*.txt')), key=lambda x: x.stat().st_ctime)
    audio_files = {file.stem: file.with_suffix('.mp3') for file in text_files}
    return render_template('edit.html', text_files=text_files, audio_files=audio_files)

@app.route('/save_text', methods=['POST'])
def save_text():
    data = request.json  # JSON形式でデータを取得
    file_name = data.get('file_name')
    new_content = data.get('content')
    
    if file_name and new_content:
        text_path = data_dir / file_name
        text_path.write_text(new_content, encoding='utf-8')
        log(f"Updated text file: {text_path}")
        return jsonify({'message': 'File updated successfully'}), 200
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/audio/<filename>')
def audio(filename):
    """MP3ファイルを提供するエンドポイント"""
    audio_path = data_dir / filename
    if audio_path.exists():
        return send_file(audio_path)
    return jsonify({'error': 'File not found'}), 404

@app.route('/delete_files', methods=['POST'])
def delete_files():
    file_name = request.json.get('file_name')
    if file_name:
        text_path = data_dir / file_name
        audio_path = data_dir / file_name.replace('.txt', '.mp3')

        try:
            if text_path.exists():
                text_path.unlink()  # テキストファイルを削除
            if audio_path.exists():
                audio_path.unlink()  # MP3ファイルを削除
            return jsonify({'message': 'Files deleted successfully'}), 200
        except Exception as e:
            return jsonify({'error': f'Failed to delete files: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file name'}), 400

@app.route('/register_texts', methods=['POST'])
def register_texts():
    """テキストファイルを連結して外部APIに登録するエンドポイント"""
    text_files = sorted(data_dir.glob('*.txt'))  # テキストファイルを昇順にソート
    combined_text = ""

    for text_file in text_files:
        combined_text += text_file.read_text(encoding='utf-8') + "\n"

    # APIに送信
    response = requests.post(
        'https://<your-domain>:8888/LLMKnowledge2/api.php',
        data={'title': '連結されたテキスト', 'text': combined_text}
    )

    if response.ok:
        result = response.json()
        return jsonify(result), 200
    else:
        return jsonify({'error': 'Failed to register texts'}), 500

@app.route('/delete_all_files', methods=['POST'])
def delete_all_files():
    """データディレクトリ内の全てのテキストファイルとMP3ファイルを削除する"""
    try:
        # テキストファイルを削除
        for text_file in data_dir.glob('*.txt'):
            text_file.unlink()
        
        # MP3ファイルを削除
        for audio_file in data_dir.glob('*.mp3'):
            audio_file.unlink()
        
        return jsonify({'message': '全てのファイルが削除されました'}), 200
    except Exception as e:
        log(f"Error deleting all files: {str(e)}")
        return jsonify({'error': 'ファイルの削除中にエラーが発生しました'}), 500
    
if __name__ == '__main__':
    log("Starting server")
    app.run(host='0.0.0.0', port=5000, debug=True)
    log("Server started")
