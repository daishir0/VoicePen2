from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
import os
import tempfile
import yaml
from datetime import datetime
from pathlib import Path
import subprocess
from pydub import AudioSegment
import requests
import shutil
import re  # 正規表現用のモジュールを追加

app = Flask(__name__)

def log(message):
    print(f"{datetime.now()} - {message}")

# Load configuration
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

# Initialize OpenAI client with API key from config
client = OpenAI(api_key=config['openai']['api_key'])

# データ保存用のディレクトリを作成
data_dir = Path('./data')
tobeprocess_dir = Path('./ToBeProcessed')
if not data_dir.exists():
    log("Data directory does not exist, creating it.")
    data_dir.mkdir(exist_ok=True)

if not tobeprocess_dir.exists():
    log("ToBeProcessed directory does not exist, creating it.")
    tobeprocess_dir.mkdir(exist_ok=True)

def sanitize_directory_name(filename):
    """ファイル名から安全なディレクトリ名を生成する"""
    # 拡張子を除去
    name_without_ext = os.path.splitext(filename)[0]
    # 特殊文字を除去し、アンダースコアに置換
    safe_name = re.sub(r'[^\w\s-]', '', name_without_ext)
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    # 先頭と末尾の特殊文字を除去
    safe_name = safe_name.strip('_')
    # 空の場合はデフォルト名を使用
    return safe_name if safe_name else 'unnamed'

def get_unique_directory_name(base_dir, original_filename):
    """ファイル名を基にユニークなディレクトリ名を生成する"""
    base_name = sanitize_directory_name(original_filename)
    base_path = base_dir / base_name
    counter = 1
    while base_path.exists():
        base_path = base_dir / f"{base_name}-{counter:02d}"
        counter += 1
    return base_path

@app.route('/')
def index():
    """デフォルトページとしてindex.htmlを表示"""
    return render_template('index.html', config=config)

@app.route('/record')
def record():
    # セキュリティチェック: sパラメータの検証
    dir_name = request.args.get('s')
    if not dir_name or '..' in dir_name or '/' in dir_name or '\\' in dir_name:
        return "無効なデータ名", 400

    # ディレクトリパスの構築
    dir_path = data_dir / dir_name

    # ディレクトリが存在しない場合
    if not dir_path.exists():
        return "ディレクトリが見つかりません", 404

    # メディアファイルの検索（video.mp4を優先）
    media_files = list(dir_path.glob('video.mp4')) or list(dir_path.glob('audio.mp3'))
    if not media_files:
        return "メディアファイルが見つかりません", 404

    is_video = media_files[0].suffix == '.mp4'
    media_path = f"/{'video' if is_video else 'audio'}/{dir_name}/{media_files[0].name}"
    media_type = 'video/mp4' if is_video else 'audio/mpeg'

    # デバッグログ
    print(f"Debug - File Info:")
    print(f"  - Original File: {media_files[0]}")
    print(f"  - Is Video: {is_video}")
    print(f"  - Media Type: {media_type}")
    print(f"  - Media Path: {media_path}")

    # テキストファイルの取得（ソート）
    text_files = sorted(list(dir_path.glob('*.txt')), key=lambda x: x.name)

    # 再生開始時間の取得と処理
    time_param = request.args.get('t', '0')
    # 's'サフィックスがある場合は削除して数値のみに
    start_time = time_param[:-1] if time_param.endswith('s') else time_param

    return render_template('record.html', 
                           media_path=media_path, 
                           media_type=media_type, 
                           text_files=text_files,
                           start_time=start_time)

@app.route('/audio/<dir_name>/<filename>')
@app.route('/video/<dir_name>/<filename>')
def serve_media(dir_name, filename):
    # セキュリティチェック
    if '..' in dir_name or '/' in dir_name or '\\' in dir_name or \
       '..' in filename or '/' in filename or '\\' in filename:
        return "無効なファイル名", 400

    media_path = data_dir / dir_name / filename
    if not media_path.exists():
        return "ファイルが見つかりません", 404

    return send_file(media_path)

@app.route('/list')
def list_recordings():
    directories = []
    for dir_path in data_dir.iterdir():
        if dir_path.is_dir():
            # ディレクトリ内のファイル数をカウント
            file_count = len(list(dir_path.glob('*')))
            
            # 作成日時と更新日時を取得
            created_at = datetime.fromtimestamp(dir_path.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            updated_at = datetime.fromtimestamp(dir_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            directories.append({
                'name': dir_path.name,
                'created_at': created_at,
                'updated_at': updated_at,
                'file_count': file_count
            })
    
    # 作成日時の降順でソート
    directories.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('list.html', directories=directories)

@app.route('/rename_directory', methods=['POST'])
def rename_directory():
    data = request.json
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    if not old_name or not new_name:
        return jsonify({'error': '無効な名前です'}), 400
    
    old_path = data_dir / old_name
    new_path = data_dir / new_name
    
    try:
        if new_path.exists():
            return jsonify({'error': '同じ名前のデータが既に存在します'}), 400
        
        old_path.rename(new_path)
        return jsonify({'message': 'データ名を変更しました'}), 200
    except Exception as e:
        return jsonify({'error': f'データ名の変更に失敗しました: {str(e)}'}), 500

@app.route('/delete_directory', methods=['POST'])
def delete_directory():
    data = request.json
    dir_name = data.get('dir_name')
    
    if not dir_name:
        return jsonify({'error': '無効なデータ名です'}), 400
    
    dir_path = data_dir / dir_name
    
    try:
        # ディレクトリを完全に削除
        shutil.rmtree(dir_path)
        return jsonify({'message': 'データを削除しました'}), 200
    except Exception as e:
        return jsonify({'error': f'データの削除に失敗しました: {str(e)}'}), 500

@app.route('/upload_media', methods=['POST'])
def upload_media():
    if 'media_data' not in request.files:
        return jsonify({'error': 'No media data provided'}), 400

    files = request.files.getlist('media_data')
    processed_files = []

    for media_file in files:
        # 各ファイルごとにユニークなディレクトリを作成
        base_dir = get_unique_directory_name(tobeprocess_dir, media_file.filename)
        base_dir.mkdir(parents=True, exist_ok=True)

        # ファイルの拡張子を取得
        original_filename = media_file.filename
        file_ext = os.path.splitext(original_filename)[1].lower()

        # ファイル名を決定
        if file_ext in ['.mp3', '.wav', '.m4a', '.webm']:
            target_filename = 'audio.mp3'
        elif file_ext in ['.mp4', '.avi', '.mov', '.mkv']:
            target_filename = 'video.mp4'
        else:
            return jsonify({'error': f'Unsupported file type: {file_ext}'}), 400

        # ファイルを保存
        full_path = base_dir / target_filename
        media_file.save(full_path)
        processed_files.append(str(full_path))

    return jsonify({
        'message': 'Files uploaded successfully',
        'files': processed_files
    }), 200

@app.route('/register_to_knowledge_db', methods=['POST'])
def register_to_knowledge_db():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'JSONデータが見つかりません'}), 400
            
        dir_name = data.get('dir_name')
        if not dir_name:
            return jsonify({'error': '無効なデータ名です'}), 400
        
        dir_path = data_dir / dir_name
        if not dir_path.exists():
            return jsonify({'error': 'データが見つかりません'}), 404
        
        # テキストファイルを取得してソート
        text_files = sorted(list(dir_path.glob('*.txt')), key=lambda x: x.name)
        if not text_files:
            return jsonify({'error': 'テキストファイルが見つかりません'}), 404
        
        # 結合するテキストを準備
        combined_text = []
        
        for text_file in text_files:
            # ファイル名から秒数を計算
            match = re.match(r'(\d{2})(\d{2})(\d{2})\.txt', text_file.name)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = int(match.group(3))
                total_seconds = hours * 3600 + minutes * 60 + seconds
                
                # ファイルの内容を読み込み
                content = text_file.read_text(encoding='utf-8').strip()
                
                # テキストを追加
                combined_text.append(content)
                combined_text.append(f"この発言の参照URL：{config['voicepen2']['base_url']}record?s={dir_name}&t={total_seconds}s")
                combined_text.append("")  # 空行を追加
        
        # 最終的なテキストを作成
        final_text = "\n".join(combined_text)
        
        # リクエストヘッダーの設定
        headers = {
            'Authorization': f'Bearer {config["llmknowledge2"]["api_key"]}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # KnowledgeDBへの登録処理
        response = requests.post(
            config['llmknowledge2']['api_url'],
            headers=headers,
            data={
                'action': 'create_record',
                'title': f'音声文字起こし: {dir_name}',
                'text': final_text,
                'reference': f"{config['voicepen2']['base_url']}record?s={dir_name}"
            }
        )

        if response.ok:
            result = response.json()
            if result.get('success'):
                return jsonify({'message': 'KnowledgeDBへの登録が完了しました'}), 200
            else:
                return jsonify({'error': result.get('message', 'KnowledgeDBへの登録に失敗しました')}), 500
        else:
            return jsonify({'error': f'KnowledgeDBへの登録に失敗しました: HTTP {response.status_code}'}), 500
        
    except Exception as e:
        print(f"Error in register_to_knowledge_db: {str(e)}")  # デバッグ用ログ
        return jsonify({'error': f'KnowledgeDBへの登録に失敗しました: {str(e)}'}), 500

if __name__ == '__main__':
    log("Starting server")
    app.run(
        host=config['server']['host'],
        port=config['server']['port'],
        debug=True
    )
    log("Server started")
