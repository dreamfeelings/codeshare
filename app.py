from flask import Flask, render_template, request, redirect, url_for, jsonify, abort, send_file
import sqlite3
import uuid
import os
import io
import zipfile
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

# 网站域名配置，部署时修改为你的域名
SITE_URL = 'https://code.mqmrx.cn'

DATABASE = 'pastes.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pastes (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                language TEXT DEFAULT 'plaintext',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_directory INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS directory_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paste_id TEXT,
                filename TEXT,
                content TEXT,
                language TEXT DEFAULT 'plaintext',
                FOREIGN KEY (paste_id) REFERENCES pastes(id)
            )
        ''')
        conn.commit()

def generate_id():
    return uuid.uuid4().hex[:8]

def detect_language(filename):
    """根据文件扩展名检测语言"""
    ext_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.html': 'html', '.css': 'css', '.json': 'json',
        '.java': 'java', '.cpp': 'cpp', '.c': 'c',
        '.go': 'go', '.rs': 'rust', '.rb': 'ruby',
        '.php': 'php', '.sql': 'sql', '.sh': 'bash',
        '.yaml': 'yaml', '.yml': 'yaml', '.xml': 'xml',
        '.md': 'markdown', '.txt': 'plaintext'
    }
    _, ext = os.path.splitext(filename.lower())
    return ext_map.get(ext, 'plaintext')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/paste', methods=['POST'])
def create_paste():
    """创建单文件粘贴"""
    title = request.form.get('title', '未命名')
    content = request.form.get('content', '')
    language = request.form.get('language', 'plaintext')
    
    if not content.strip():
        return redirect(url_for('index'))
    
    paste_id = generate_id()
    with get_db() as conn:
        conn.execute(
            'INSERT INTO pastes (id, title, content, language, is_directory) VALUES (?, ?, ?, ?, 0)',
            (paste_id, title, content, language)
        )
        conn.commit()
    
    return redirect(url_for('view_paste', paste_id=paste_id))

@app.route('/directory', methods=['POST'])
def create_directory():
    """创建多文件目录"""
    data = request.get_json()
    title = data.get('title', '未命名项目')
    files = data.get('files', [])
    
    if not files:
        return jsonify({'error': '至少需要一个文件'}), 400
    
    paste_id = generate_id()
    with get_db() as conn:
        conn.execute(
            'INSERT INTO pastes (id, title, content, is_directory) VALUES (?, ?, ?, 1)',
            (paste_id, title, '')
        )
        for f in files:
            language = detect_language(f['filename'])
            conn.execute(
                'INSERT INTO directory_files (paste_id, filename, content, language) VALUES (?, ?, ?, ?)',
                (paste_id, f['filename'], f['content'], language)
            )
        conn.commit()
    
    return jsonify({'id': paste_id, 'url': url_for('view_paste', paste_id=paste_id)})

@app.route('/p/<paste_id>')
def view_paste(paste_id):
    """查看粘贴内容"""
    with get_db() as conn:
        paste = conn.execute('SELECT * FROM pastes WHERE id = ?', (paste_id,)).fetchone()
        if not paste:
            abort(404)
        
        files = []
        if paste['is_directory']:
            files = conn.execute(
                'SELECT * FROM directory_files WHERE paste_id = ? ORDER BY filename',
                (paste_id,)
            ).fetchall()
    
    share_url = f"{SITE_URL}/p/{paste_id}"
    return render_template('view.html', paste=paste, files=files, share_url=share_url)

@app.route('/p/<paste_id>/raw')
def raw_paste(paste_id):
    """获取原始内容"""
    with get_db() as conn:
        paste = conn.execute('SELECT * FROM pastes WHERE id = ?', (paste_id,)).fetchone()
        if not paste:
            abort(404)
    return paste['content'], 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/p/<paste_id>/file/<int:file_id>/raw')
def raw_file(paste_id, file_id):
    """获取目录中某个文件的原始内容"""
    with get_db() as conn:
        file = conn.execute(
            'SELECT * FROM directory_files WHERE paste_id = ? AND id = ?',
            (paste_id, file_id)
        ).fetchone()
        if not file:
            abort(404)
    return file['content'], 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/p/<paste_id>/download')
def download_zip(paste_id):
    """下载目录为ZIP文件"""
    with get_db() as conn:
        paste = conn.execute('SELECT * FROM pastes WHERE id = ?', (paste_id,)).fetchone()
        if not paste or not paste['is_directory']:
            abort(404)
        
        files = conn.execute(
            'SELECT filename, content FROM directory_files WHERE paste_id = ?',
            (paste_id,)
        ).fetchall()
    
    # 创建ZIP文件
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(f['filename'], f['content'].encode('utf-8'))
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{paste['title']}.zip"
    )

@app.route('/api/recent')
def recent_pastes():
    """获取最近的粘贴（可选功能）"""
    with get_db() as conn:
        pastes = conn.execute(
            'SELECT id, title, is_directory, created_at FROM pastes ORDER BY created_at DESC LIMIT 10'
        ).fetchall()
    return jsonify([dict(p) for p in pastes])

def cleanup_old_pastes():
    """清理7天前的粘贴"""
    with get_db() as conn:
        # 获取7天前的时间
        cutoff = datetime.now() - timedelta(days=7)
        cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
        
        # 先删除关联的文件
        conn.execute('''
            DELETE FROM directory_files 
            WHERE paste_id IN (SELECT id FROM pastes WHERE created_at < ?)
        ''', (cutoff_str,))
        
        # 再删除粘贴记录
        result = conn.execute('DELETE FROM pastes WHERE created_at < ?', (cutoff_str,))
        conn.commit()
        
        deleted_count = result.rowcount
        if deleted_count > 0:
            print(f'[清理任务] 已清理 {deleted_count} 条过期记录')

def cleanup_scheduler():
    """定时清理调度器，每天检查一次"""
    while True:
        time.sleep(86400)  # 每24小时检查一次
        cleanup_old_pastes()

if __name__ == '__main__':
    init_db()
    
    # 启动时先执行一次清理
    cleanup_old_pastes()
    
    # 启动后台清理线程
    cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
    cleanup_thread.start()
    print('[清理任务] 已启动，7天前的内容将被自动清理')
    
    app.run(debug=True, host='0.0.0.0', port=5000)
