# CodeShare 代码分享

一个简洁的代码/文本分享网站，支持单文件和多文件目录分享。

## 功能特性

- **单文件分享**：粘贴代码，选择语言，生成短链接
- **多文件目录**：创建多个文件组成项目，一键分享整个目录
- **代码高亮**：支持多种编程语言语法高亮
- **一键复制**：快速复制代码或分享链接
- **自动清理**：7天后自动清理过期内容

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python app.py
```

访问 http://127.0.0.1:5000

## 项目结构

```
codeshare/
├── app.py              # Flask 主应用
├── requirements.txt    # 依赖
├── templates/
│   ├── index.html      # 首页（创建分享）
│   └── view.html       # 查看页
└── static/
    ├── css/            # 样式文件
    └── js/             # 脚本文件
```

## 支持的语言

Python, JavaScript, TypeScript, Java, C, C++, Go, Rust, HTML, CSS, SQL, JSON, YAML, Bash, Markdown 等

## 作者

阿尼亚与她
