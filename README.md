## Overview
VoicePen2 is a web application that provides real-time voice recording and transcription capabilities using OpenAI's Whisper API. It allows users to record audio, automatically transcribe it to text, and edit the transcribed content. The application supports both streaming audio recording and local file uploads, with automatic splitting of long audio files.

## Installation
1. Clone the repository:
```bash
git clone https://github.com/daishir0/VoicePen2.git
cd VoicePen2
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg (required for audio processing):
- For Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```
- For macOS (using Homebrew):
```bash
brew install ffmpeg
```
- For Windows, download from the official FFmpeg website and add to PATH

4. Configure the application:
```bash
cp config.yaml.org config.yaml
```
Then edit `config.yaml` with your configuration values:

```yaml
openai:
  api_key: "your-openai-api-key"    # Required: Your OpenAI API key for Whisper API
    
huggingface:
  use_auth_token: "your-huggingface-token"    # Optional: Your Hugging Face authentication token

llmknowledge2:
  api_url: "https://your-domain/LLMKnowledge2/api.php"    # Optional: URL for LLMKnowledge2 API
```

Configuration details:
- `openai.api_key`: Required for using the Whisper API. Get it from your OpenAI account dashboard
- `huggingface.use_auth_token`: Optional authentication token for Hugging Face services
- `llmknowledge2.api_url`: Optional API URL for the LLMKnowledge2 system integration

5. Create a data directory:
```bash
mkdir data
```

## Usage
1. Start the server:
```bash
python app.py
```

2. Access the application:
- Open your web browser and navigate to `http://localhost:5000`
- For recording: Use the main page
- For editing transcriptions: Navigate to `/edit`

3. Features:
- Real-time voice recording and transcription
- Support for uploading local audio files
- Automatic splitting of long recordings
- Text editing capability for transcriptions
- Bulk text registration to external API
- File management (delete individual or all files)

## Notes
- Supported audio formats: MP3, M4A, MP4, WebM
- Audio files longer than 30 seconds are automatically split
- All recordings and transcriptions are stored in the `data` directory
- The application requires a stable internet connection for API access
- Make sure your OpenAI API key has sufficient credits for Whisper API usage

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# VoicePen2
## 概要
VoicePen2は、OpenAIのWhisper APIを使用したリアルタイムの音声録音と文字起こし機能を提供するWebアプリケーションです。音声を録音し、自動的にテキストに変換し、文字起こしされた内容を編集することができます。ストリーミング録音とローカルファイルのアップロードの両方をサポートし、長い音声ファイルは自動的に分割されます。

## インストール方法
1. レポジトリをクローンします：
```bash
git clone https://github.com/daishir0/VoicePen2.git
cd VoicePen2
```

2. 必要なパッケージをインストールします：
```bash
pip install -r requirements.txt
```

3. FFmpegをインストールします（音声処理に必要）：
- Ubuntu/Debian：
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```
- macOS（Homebrewを使用）：
```bash
brew install ffmpeg
```
- Windowsの場合、FFmpeg公式サイトからダウンロードしてPATHに追加

4. アプリケーションを設定します：
```bash
cp config.yaml.org config.yaml
```
その後、`config.yaml`に設定値を記入します：

```yaml
openai:
  api_key: "your-openai-api-key"    # 必須：OpenAIのAPIキー（Whisper API用）
    
huggingface:
  use_auth_token: "your-huggingface-token"    # オプション：Hugging Face認証トークン

llmknowledge2:
  api_url: "https://your-domain/LLMKnowledge2/api.php"    # オプション：LLMKnowledge2 APIのURL
```

設定の詳細：
- `openai.api_key`：Whisper APIを使用するために必須です。OpenAIアカウントのダッシュボードから取得してください
- `huggingface.use_auth_token`：Hugging Faceサービスを使用する場合の認証トークンです（オプション）
- `llmknowledge2.api_url`：LLMKnowledge2システムとの連携用APIのURLです（オプション）

5. データディレクトリを作成します：
```bash
mkdir data
```

## 使い方
1. サーバーを起動します：
```bash
python app.py
```

2. アプリケーションにアクセスします：
- Webブラウザで`http://localhost:5000`にアクセス
- 録音：メインページを使用
- 文字起こしの編集：`/edit`にアクセス

3. 機能：
- リアルタイムの音声録音と文字起こし
- ローカル音声ファイルのアップロード対応
- 長い録音の自動分割
- 文字起こしテキストの編集機能
- 外部APIへの一括テキスト登録
- ファイル管理（個別または全件削除）

## 注意点
- 対応音声フォーマット：MP3、M4A、MP4、WebM
- 30秒を超える音声ファイルは自動的に分割されます
- 全ての録音と文字起こしは`data`ディレクトリに保存されます
- アプリケーションの使用にはインターネット接続が必要です
- OpenAI APIキーにWhisper API使用のための十分なクレジットがあることを確認してください

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。
