#!/usr/bin/env python3
import os
import sys
import yaml
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI

# 基本となるパスの定義
SCRIPT_DIR = Path('/home/ec2-user/VoicePen2')
CONFIG_PATH = SCRIPT_DIR / 'config.yaml'
BASE_DIR = SCRIPT_DIR / 'ToBeProcessed'
DATA_DIR = SCRIPT_DIR / 'data'
LOCK_PATH = Path('/tmp/voicepen.lock')

# ffmpegコマンドのフルパス（環境に応じて変更）
FFMPEG_CMD = 'ffmpeg'  # または '/usr/bin/ffmpeg' のように絶対パスで指定

def log(message):
    print(f"{datetime.now()} - {message}")

def create_lock_file():
    with LOCK_PATH.open('w') as f:
        f.write(str(os.getpid()))
    return LOCK_PATH

def remove_lock_file(lock_path):
    if lock_path.exists():
        lock_path.unlink()

def get_oldest_directory(base_dir):
    dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    if not dirs:
        return None
    return min(dirs, key=lambda x: os.path.getctime(os.path.join(base_dir, x)))

def convert_video_to_audio(video_path, output_path):
    try:
        subprocess.run([
            FFMPEG_CMD, '-i', str(video_path), 
            '-vn', '-acodec', 'libmp3lame', 
            '-q:a', '2', str(output_path)
        ], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Error converting video to audio: {e.stderr}")
        return False

def split_audio(input_path, output_dir):
    try:
        subprocess.run([
            FFMPEG_CMD, '-i', str(input_path), 
            '-f', 'segment', 
            '-segment_time', '60', 
            '-segment_format', 'mp3', 
            f'{output_dir}/%06d.mp3'
        ], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Error splitting audio: {e.stderr}")
        return False

def rename_segments(split_dir):
    """セグメントファイルを時間ベースでリネーム"""
    segments = sorted([f for f in os.listdir(split_dir) if f.endswith('.mp3')])
    
    for index, segment in enumerate(segments):
        old_path = os.path.join(split_dir, segment)
        
        # 時間計算（1分 = 60秒）
        total_seconds = index * 60
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # 新しいファイル名を生成（HHMMSS形式）
        new_name = f"{hours:02d}{minutes:02d}{seconds:02d}.mp3"
        new_path = os.path.join(split_dir, new_name)
        
        os.rename(old_path, new_path)

def main():
    log("処理を開始します")
    lock_path = create_lock_file()
    log("ロックファイルを作成しました")
    
    try:
        # Load configuration
        log("設定ファイルを読み込んでいます")
        with CONFIG_PATH.open('r') as config_file:
            config = yaml.safe_load(config_file)
        log("設定ファイルの読み込みが完了しました")
        
        # Initialize OpenAI client
        log("OpenAI クライアントを初期化しています")
        client = OpenAI(api_key=config['openai']['api_key'])
        log("OpenAI クライアントの初期化が完了しました")
        
        # Find the oldest directory in ToBeProcessed
        log("処理対象のディレクトリを探しています")
        oldest_dir = get_oldest_directory(BASE_DIR)
        
        if not oldest_dir:
            log("処理対象のディレクトリが見つかりませんでした")
            return
        
        log(f"処理対象のディレクトリ: {oldest_dir}")
        full_dir_path = BASE_DIR / oldest_dir
        
        # Check for audio or video file
        audio_path = full_dir_path / 'audio.mp3'
        video_path = full_dir_path / 'video.mp4'
        
        if not os.path.exists(audio_path):
            if os.path.exists(video_path):
                log("動画ファイルを音声ファイルに変換しています")
                if not convert_video_to_audio(video_path, audio_path):
                    log("動画から音声への変換に失敗しました")
                    return
                log("動画から音声への変換が完了しました")
            else:
                log("音声ファイルも動画ファイルも見つかりませんでした")
                return
        
        # Create a temporary directory for splitting
        log("一時ディレクトリを作成しています")
        split_dir = full_dir_path / 'src'
        os.makedirs(split_dir, exist_ok=True)
        
        # Split audio into 1-minute segments
        log("音声ファイルを1分間のセグメントに分割しています")
        if not split_audio(audio_path, split_dir):
            log("音声ファイルの分割に失敗しました")
            return
        log("音声ファイルの分割が完了しました")
        
        # Rename segments to match the required format
        log("セグメントファイルの名前を変更しています")
        rename_segments(split_dir)
        log("セグメントファイルの名前変更が完了しました")
        
        # Sort audio segments
        audio_segments = sorted([f for f in os.listdir(split_dir) if f.endswith('.mp3')])
        log(f"合計 {len(audio_segments)} 個のセグメントを処理します")
        
        # Transcribe each segment
        for i, segment in enumerate(audio_segments, 1):
            try:
                log(f"セグメント {i}/{len(audio_segments)} を文字起こししています: {segment}")
                segment_path = os.path.join(split_dir, segment)
                with open(segment_path, 'rb') as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                
                # Save segment MP3 to the main directory
                shutil.move(segment_path, os.path.join(full_dir_path, segment))
                
                # Save transcript to the main directory
                txt_path = os.path.join(full_dir_path, segment.replace('.mp3', '.txt'))
                with open(txt_path, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(transcript.text)
                
                log(f"セグメント {segment} の文字起こしが完了しました")
            except Exception as e:
                log(f"セグメント {segment} の文字起こし中にエラーが発生しました: {str(e)}")
        
        # Remove the temporary src directory
        log("一時ディレクトリを削除しています")
        os.rmdir(split_dir)
        log("一時ディレクトリの削除が完了しました")
        
        # Move processed directory to data
        log("処理済みのディレクトリを移動しています")
        os.makedirs(DATA_DIR, exist_ok=True)
        destination_dir = DATA_DIR / oldest_dir
        shutil.move(full_dir_path, destination_dir)
        
        log(f"{oldest_dir} の処理が正常に完了しました")
        
    except Exception as e:
        log(f"予期せぬエラーが発生しました: {str(e)}")
    
    finally:
        # Always remove lock file
        log("ロックファイルを削除しています")
        remove_lock_file(lock_path)
        log("処理を終了します")

if __name__ == '__main__':
    main()
