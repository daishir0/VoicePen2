#!/usr/bin/env python3
import os
import sys
import yaml
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI

def log(message):
    print(f"{datetime.now()} - {message}")

def create_lock_file():
    lock_path = '/tmp/voicepen.lock'
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))
    return lock_path

def remove_lock_file(lock_path):
    if os.path.exists(lock_path):
        os.unlink(lock_path)

def get_oldest_directory(base_dir):
    dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    if not dirs:
        return None
    return min(dirs, key=lambda x: os.path.getctime(os.path.join(base_dir, x)))

def convert_video_to_audio(video_path, output_path):
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path, 
            '-vn', '-acodec', 'libmp3lame', 
            '-q:a', '2', output_path
        ], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Error converting video to audio: {e.stderr}")
        return False

def split_audio(input_path, output_dir):
    try:
        subprocess.run([
            'ffmpeg', '-i', input_path, 
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
    lock_path = create_lock_file()
    
    try:
        # Load configuration
        with open('config.yaml', 'r') as config_file:
            config = yaml.safe_load(config_file)
        
        # Initialize OpenAI client
        client = OpenAI(api_key=config['openai']['api_key'])
        
        # Find the oldest directory in ToBeProcessed
        base_dir = 'ToBeProcessed'
        oldest_dir = get_oldest_directory(base_dir)
        
        if not oldest_dir:
            log("No directories to process.")
            return
        
        full_dir_path = os.path.join(base_dir, oldest_dir)
        
        # Check for audio or video file
        audio_path = os.path.join(full_dir_path, 'audio.mp3')
        video_path = os.path.join(full_dir_path, 'video.mp4')
        
        if not os.path.exists(audio_path):
            if os.path.exists(video_path):
                if not convert_video_to_audio(video_path, audio_path):
                    log("Failed to convert video to audio.")
                    return
            else:
                log("No audio or video file found.")
                return
        
        # Create a temporary directory for splitting
        split_dir = os.path.join(full_dir_path, 'src')
        os.makedirs(split_dir, exist_ok=True)
        
        # Split audio into 1-minute segments
        if not split_audio(audio_path, split_dir):
            log("Failed to split audio.")
            return
        
        # Rename segments to match the required format
        rename_segments(split_dir)
        
        # Sort audio segments
        audio_segments = sorted([f for f in os.listdir(split_dir) if f.endswith('.mp3')])
        
        # Transcribe each segment
        for segment in audio_segments:
            try:
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
                
                log(f"Transcribed {segment}")
            except Exception as e:
                log(f"Error transcribing {segment}: {str(e)}")
        
        # Remove the temporary src directory
        os.rmdir(split_dir)
        
        # Move processed directory to data
        os.makedirs('data', exist_ok=True)
        destination_dir = os.path.join('data', oldest_dir)
        shutil.move(full_dir_path, destination_dir)
        
        log(f"Successfully processed {oldest_dir}")
        
    except Exception as e:
        log(f"Unexpected error: {str(e)}")
    
    finally:
        # Always remove lock file
        remove_lock_file(lock_path)

if __name__ == '__main__':
    main()
