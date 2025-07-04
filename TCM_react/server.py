# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import sys
import os
import traceback
import sqlite3
import json
from datetime import datetime
import hashlib
import requests

# 添加RAG-TCM目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
rag_tcm_dir = os.path.join(os.path.dirname(current_dir), "RAG-TCM")
sys.path.append(rag_tcm_dir)

from main import main
from ollama_1 import DeepSeekQuestionProcessor
from json_to_triples import json_to_triples

app = Flask(__name__)

# 配置CORS
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],  # 允许的前端域名
        "methods": ["OPTIONS", "GET", "POST", "PUT", "DELETE"],  # 允许的方法
        "allow_headers": ["Content-Type", "Authorization", "Accept"],  # 允许的请求头
        "expose_headers": ["Content-Type", "Authorization"],  # 暴露的响应头
        "supports_credentials": True  # 支持凭证
    }
})

# 添加错误处理装饰器
@app.errorhandler(Exception)
def handle_error(error):
    print(f"Error occurred: {str(error)}")
    print(traceback.format_exc())
    return jsonify({
        "status": "error",
        "message": str(error),
        "traceback": traceback.format_exc()
    }), 500

# 初始化数据库
def init_db():
    try:
        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            
            # 创建用户表
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建对话会话表
            c.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # 创建消息表
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                )
            ''')
            
            # 检查conversations表是否已存在name列
            c.execute("PRAGMA table_info(conversations)")
            columns = [column[1] for column in c.fetchall()]
            if 'name' not in columns:
                print("Adding name column to conversations table")
                c.execute('ALTER TABLE conversations ADD COLUMN name TEXT DEFAULT NULL')
            
            conn.commit()
            print("Database initialized successfully")
    except Exception as e:
        print("Error initializing database:", str(e))
        raise

# 初始化数据库
init_db()

# 创建新对话
@app.route('/api/conversation', methods=['POST'])
def create_conversation():
    try:
        # 从请求体获取用户ID和对话名称
        data = request.json
        user_id = data.get('user_id')
        name = data.get('name')  # 可选参数

        if not user_id:
            return jsonify({'error': '未登录'}), 401

        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            if name:
                c.execute('INSERT INTO conversations (user_id, name) VALUES (?, ?)', (user_id, name))
            else:
                c.execute('INSERT INTO conversations (user_id) VALUES (?)', (user_id,))
                conversation_id = c.lastrowid
                conn.commit()
                return jsonify({'conversation_id': conversation_id})
    except Exception as e:
        print("Error creating conversation:", str(e))
        return jsonify({'error': str(e)}), 500

# 获取所有对话列表
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    try:
        # 从请求头获取用户ID
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '未登录'}), 401

        print(f"Fetching conversations for user_id: {user_id}")  # 添加日志

        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            
            # 先验证用户是否存在
            c.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if not c.fetchone():
                print(f"User {user_id} not found")  # 添加日志
                return jsonify({'error': '用户不存在'}), 404
            
            # 获取对话列表
            c.execute('''
                SELECT 
                    c.conversation_id,
                    c.created_at,
                    COALESCE(c.name, '') as name,
                    COALESCE(
                        (SELECT content 
                         FROM messages 
                         WHERE conversation_id = c.conversation_id 
                         ORDER BY timestamp ASC 
                         LIMIT 1
                        ),
                        '新对话'
                    ) as first_message
                FROM conversations c
                WHERE c.user_id = ?
                ORDER BY c.created_at DESC
            ''', (user_id,))
            
            rows = c.fetchall()
            print(f"Found {len(rows)} conversations")  # 添加日志
            
            conversations = []
            for row in rows:
                conversations.append({
                    'id': row[0],
                    'created_at': row[1],
                    'name': row[2] if row[2] else None,
                    'first_message': row[3]
                })
            
            return jsonify(conversations)
    except sqlite3.Error as e:
        print(f"Database error in get_conversations: {str(e)}")  # 添加日志
        return jsonify({'error': f'数据库错误: {str(e)}'}), 500
    except Exception as e:
        print(f"Unexpected error in get_conversations: {str(e)}")  # 添加日志
        print(traceback.format_exc())  # 打印完整的错误堆栈
        return jsonify({'error': str(e)}), 500

# 获取特定对话的所有消息
@app.route('/api/conversation/<int:conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    try:
        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            c.execute('SELECT message_id, role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC', (conversation_id,))
            messages = [{'id': row[0], 'role': row[1], 'content': row[2], 'timestamp': row[3]} for row in c.fetchall()]
            return jsonify(messages)
    except Exception as e:
        print("Error fetching messages:", str(e))
        return jsonify({'error': str(e)}), 500

def get_conversation_history(conversation_id, limit=5):
    """获取指定对话的最近历史消息"""
    try:
        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT role, content 
                FROM messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (conversation_id, limit))
            # 返回最近的消息，但是要按时间正序排列
            messages = [{'role': role, 'content': content} for role, content in c.fetchall()]
            return list(reversed(messages))
    except Exception as e:
        print("Error fetching conversation history:", str(e))
        return []

def format_context(history, current_question):
    """将历史消息格式化为上下文字符串，明确区分历史对话和当前问题"""
    context = []
    
    # 添加历史对话（如果有）
    if history:
        context.append("历史对话：")
        for msg in history[:-1]:  # 不包含最后一条消息，因为它就是当前问题
            role = "用户" if msg['role'] == 'user' else "系统"
            context.append(f'{role}："{msg["content"]}"')
    
    # 添加当前问题
    context.append("\n当前问题：")
    context.append(f'"{current_question}"')
    
    return "\n".join(context)

# 发送新消息
@app.route('/api/conversation/<int:conversation_id>/message', methods=['POST'])
def send_message(conversation_id):
    data = request.json
    content = data.get('content')
    role = data.get('role', 'user')
    
    if not content:
        return jsonify({'error': 'No content provided'}), 400
    
    try:
        # 获取对话历史
        history = get_conversation_history(conversation_id)
        
        # 如果是用户消息，先生成回复
        if role == 'user':
            try:
                # 处理特殊问题：询问上一个问题
                if "上句话" in content or "上一句" in content:
                    # 查找历史记录中最近的用户消息
                    for msg in reversed(history):
                        if msg['role'] == 'user':
                            system_response = f'您上一句话是："{msg["content"]}"'
                            break
                    else:
                        system_response = "抱歉，我找不到您上一句话的记录。"
                else:
                    # 使用ollama处理问题，这里不传入上下文
                    processor = DeepSeekQuestionProcessor()
                    question_for_knowledge = processor.process_question(content)
                    
                    # 格式化上下文，明确区分历史对话和当前问题
                    context = format_context(history, content)
                    
                    # 调用main.py中的逻辑获取答案，传入格式化后的上下文
                    system_response = main(context, question_for_knowledge)
            except Exception as e:
                print("Error generating response:", str(e))
                system_response = "抱歉，生成回复时出现错误：" + str(e)

        # 使用with语句自动管理连接，设置超时时间
        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            
            # 存储用户消息
            c.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                    (conversation_id, role, content))
            
            # 如果是用户消息，存储系统回复
            if role == 'user':
                c.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                        (conversation_id, 'system', system_response))
            
            conn.commit()
            
        return jsonify({'status': 'success'})
        
    except sqlite3.OperationalError as e:
        print("Database error:", str(e))
        return jsonify({'error': 'Database operation failed. Please try again.'}), 500
    except Exception as e:
        print("Unexpected error:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:5175")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    try:
        print("Received request")
        print("Request headers:", dict(request.headers))
        print("Request method:", request.method)
        
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400
            
        print("Request data:", data)
        
        user_message = data.get("message")
        if not user_message:
            return jsonify({"status": "error", "message": "No message provided"}), 400
            
        print("User message:", user_message)
        
        # 使用ollama_1处理问题
        processor = DeepSeekQuestionProcessor()
        question_for_knowledge = processor.process_question(user_message)
        print("Processed question:", question_for_knowledge)
        
        # 调用main.py中的逻辑获取答案
        original_question = user_message
        answer = main(original_question, question_for_knowledge)
        print("Generated answer:", answer)
        
        response = jsonify({
            "status": "success",
            "answer": answer
        })
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:5174")
        return response
        
    except Exception as e:
        print("Error occurred:")
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# 删除特定对话
@app.route('/api/conversation/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    try:
        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            # 首先删除该会话的所有消息
            c.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
            # 然后删除会话本身
            c.execute('DELETE FROM conversations WHERE conversation_id = ?', (conversation_id,))
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        print("Error deleting conversation:", str(e))
        return jsonify({'error': str(e)}), 500

# 用户注册
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        print("Received registration data:", data)
        
        username = data.get('username')
        password = data.get('password')
        email = data.get('email', '').strip() or None  # 如果email为空字符串，则设为None
        
        print(f"Processing registration - username: {username}, email: {email}")

        if not username or not password:
            print("Missing username or password")
            return jsonify({'error': '用户名和密码不能为空'}), 400

        # 对密码进行哈希处理
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            
            # 先检查用户名是否已存在
            c.execute('SELECT username FROM users WHERE username = ?', (username,))
            if c.fetchone():
                print(f"Username {username} already exists")
                return jsonify({'error': f'用户名 {username} 已存在'}), 409
                
            # 如果提供了邮箱，检查邮箱是否已存在
            if email:
                c.execute('SELECT email FROM users WHERE email = ?', (email,))
                if c.fetchone():
                    print(f"Email {email} already exists")
                    return jsonify({'error': f'邮箱 {email} 已被使用'}), 409
            
            try:
                # 插入新用户
                c.execute('INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
                         (username, password_hash, email))
                conn.commit()
                print(f"Successfully registered user: {username}")
                return jsonify({'status': 'success', 'message': '注册成功'})
                
            except sqlite3.IntegrityError as e:
                print(f"Database error during registration: {str(e)}")
                if "UNIQUE constraint failed: users.email" in str(e):
                    return jsonify({'error': '该邮箱已被注册'}), 409
                elif "UNIQUE constraint failed: users.username" in str(e):
                    return jsonify({'error': '该用户名已被注册'}), 409
                else:
                    return jsonify({'error': '注册失败，请检查输入信息'}), 409

    except Exception as e:
        print(f"Unexpected error in registration: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'注册失败：{str(e)}'}), 500

# 调试用：查看所有用户（仅用于开发环境）
@app.route('/api/debug/users', methods=['GET'])
def debug_users():
    try:
        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            c.execute('SELECT user_id, username, email FROM users')
            users = [{'id': row[0], 'username': row[1], 'email': row[2]} for row in c.fetchall()]
            return jsonify(users)
    except Exception as e:
        print("Error fetching users:", str(e))
        return jsonify({'error': str(e)}), 500

# 用户登录
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400

        # 对密码进行哈希处理
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            c.execute('SELECT user_id, username FROM users WHERE username = ? AND password_hash = ?',
                     (username, password_hash))
            user = c.fetchone()

            if user:
                return jsonify({
                    'status': 'success',
                    'user': {
                        'id': user[0],
                        'username': user[1]
                    }
                })
            else:
                return jsonify({'error': '用户名或密码错误'}), 401

    except Exception as e:
        print("Error in login:", str(e))
        return jsonify({'error': str(e)}), 500

# 新增：提供流式响应的API端点
@app.route("/api/stream", methods=["POST"])
def stream():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400
            
        user_message = data.get("message")
        conversation_id = data.get("conversation_id")
        
        if not user_message:
            return jsonify({"status": "error", "message": "No message provided"}), 400
            
        # 获取对话历史（如果提供了conversation_id）
        history = []
        if conversation_id:
            history = get_conversation_history(conversation_id)
        
        # 处理问题
        processor = DeepSeekQuestionProcessor()
        question_for_knowledge = processor.process_question(user_message)
        
        # 格式化上下文，明确区分历史对话和当前问题
        if history:
            context = format_context(history, user_message)
        else:
            context = user_message
        
        # 流式响应
        def generate():
            try:
                # 这里直接使用ollama_2.py中的DeepSeekAnswerGenerator
                from ollama_2 import DeepSeekAnswerGenerator
                import json
                
                # 获取知识库
                try:
                    with open('query_results.json', 'r', encoding='utf-8') as f:
                        knowledge = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    yield f"data: {json.dumps({'error': '获取知识库失败'})}\n\n"
                    return
                
                # 保存用户消息到数据库（如果提供了conversation_id）
                if conversation_id:
                    try:
                        with sqlite3.connect('chat_history.db', timeout=20) as conn:
                            c = conn.cursor()
                            c.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                                    (conversation_id, 'user', user_message))
                            conn.commit()
                    except Exception as e:
                        print(f"Error saving user message: {str(e)}")
                
                # 使用DeepSeekAnswerGenerator获取流式回答
                generator = DeepSeekAnswerGenerator()
                
                # 传递查询知识库所需的问题
                from get_knowledge import get_knowledge
                get_knowledge(question_for_knowledge)
                
                # 重新加载更新后的知识库
                try:
                    with open('query_results.json', 'r', encoding='utf-8') as f:
                        knowledge = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    yield f"data: {json.dumps({'error': '获取知识库失败'})}\n\n"
                    return
                
                # 收集完整响应以便保存到数据库
                full_response = ""
                
                # 分批处理知识chunks
                knowledge_chunks = generator.split_knowledge_by_entities(knowledge)
                if not knowledge_chunks:
                    message = "知识库为空，无法回答问题"
                    yield f"data: {json.dumps({'content': message})}\n\n"
                    full_response = message
                else:
                    try:
                        messages = []
                        
                        # 系统提示
                        messages.append({
                            "role": "system",
                            "content": "你是一个中医知识问答助手。你需要基于提供的知识回答问题。请记住所有提供的知识，并在最后给出完整的回答。"
                        })
                        
                        # 添加原始问题
                        messages.append({
                            "role": "user",
                            "content": f"问题是：{context}\n\n我会分多次提供知识库内容，请你记住这些知识，最后回答问题。"
                        })
                        
                        messages.append({
                            "role": "assistant",
                            "content": "好的，我会仔细阅读每部分知识，并在最后给出完整的回答。请提供第一部分知识。"
                        })
                        
                        # 分批处理chunks
                        for i in range(0, len(knowledge_chunks), generator.max_chunks_per_batch):
                            batch = knowledge_chunks[i:i + generator.max_chunks_per_batch]
                            batch_text = "\n\n---\n\n".join(batch)
                            
                            # 确保batch_text不会太长
                            if len(batch_text) > generator.max_chunk_size:
                                batch_text = generator.truncate_text(batch_text, generator.max_chunk_size)
                            
                            # 检查并维护消息历史的长度
                            while generator.get_total_length(messages) + len(batch_text) > generator.max_context_length:
                                # 移除最早的非系统消息
                                for j in range(1, len(messages)):
                                    if messages[j]["role"] != "system":
                                        messages.pop(j)
                                        break
                            
                            messages.append({
                                "role": "user",
                                "content": f"这是第{i//generator.max_chunks_per_batch + 1}批知识：\n\n{batch_text}"
                            })
                            
                            # 调用API处理当前批次
                            response = requests.post(
                                f"{generator.api_base}/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {generator.api_key}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "model": "deepseek-chat",
                                    "messages": messages,
                                    "temperature": 0.1,
                                    "stream": True
                                },
                                stream=True
                            )
                            response.raise_for_status()
                            
                            # 处理流式响应
                            batch_response = ""
                            for line in response.iter_lines():
                                if line:
                                    try:
                                        json_str = line.decode('utf-8').replace('data: ', '')
                                        if json_str.strip() == '[DONE]':
                                            break
                                        chunk = json.loads(json_str)
                                        if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                                            content = chunk['choices'][0]['delta']['content']
                                            batch_response += content
                                    except json.JSONDecodeError:
                                        continue
                            
                            messages.append({
                                "role": "assistant",
                                "content": batch_response
                            })
                        
                        # 请求最终答案
                        final_prompt = f"现在你已经看完了所有知识，请基于这些知识回答最初的问题：{context}\n\n请给出完整、准确的回答，如果一个方剂在多本书中出现，请综合回答，告诉我们出自哪本书。但不要自己添加自己查询的信息。若知识库中没有相关信息，请直接说明。"
                        
                        # 确保最终请求不会太长
                        while generator.get_total_length(messages) + len(final_prompt) > generator.max_context_length:
                            for j in range(1, len(messages)):
                                if messages[j]["role"] != "system":
                                    messages.pop(j)
                                    break
                        
                        messages.append({
                            "role": "user",
                            "content": final_prompt
                        })
                        
                        # 获取最终答案（流式输出）
                        response = requests.post(
                            f"{generator.api_base}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {generator.api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "deepseek-chat",
                                "messages": messages,
                                "temperature": 0.1,
                                "stream": True
                            },
                            stream=True
                        )
                        response.raise_for_status()
                        
                        # 处理最终答案的流式响应
                        for line in response.iter_lines():
                            if line:
                                try:
                                    json_str = line.decode('utf-8').replace('data: ', '')
                                    if json_str.strip() == '[DONE]':
                                        break
                                    chunk = json.loads(json_str)
                                    if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                                        content = chunk['choices'][0]['delta']['content']
                                        # 发送到前端
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                                        full_response += content
                                except json.JSONDecodeError:
                                    continue
                        
                    except Exception as e:
                        error_msg = f"处理知识块时出错: {str(e)}"
                        yield f"data: {json.dumps({'error': error_msg})}\n\n"
                        full_response = error_msg
                
                # 保存回复到数据库（如果提供了conversation_id）
                if conversation_id and full_response:
                    try:
                        with sqlite3.connect('chat_history.db', timeout=20) as conn:
                            c = conn.cursor()
                            c.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                                    (conversation_id, 'system', full_response))
                            conn.commit()
                    except Exception as e:
                        print(f"Error saving system response: {str(e)}")
                
                # 发送完成信号
                yield f"data: {json.dumps({'finished': True})}\n\n"
                
            except Exception as e:
                error_msg = f"流式响应出错: {str(e)}"
                print(error_msg)
                print(traceback.format_exc())
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
        
        return app.response_class(generate(), mimetype='text/event-stream')
    except Exception as e:
        print("Error in stream API:", str(e))
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/knowledge-graph', methods=['POST'])
def get_knowledge_graph():
    try:
        data = request.get_json()
        query = data.get('query')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
        
        # 使用DeepSeekQuestionProcessor处理问题
        processor = DeepSeekQuestionProcessor()
        question_for_knowledge = processor.process_question(query)
        
        # 从RAG-TCM调用get_knowledge获取相关知识
        from get_knowledge import get_knowledge
        get_knowledge(question_for_knowledge)
        
        # 检查query_results.json是否存在
        json_file = 'query_results.json'
        if not os.path.exists(json_file):
            return jsonify({"nodes": [], "links": []}), 200
        
        # 读取JSON文件
        with open(json_file, 'r', encoding='utf-8') as f:
            knowledge_json = json.load(f)
        
        # 将三元组转换为图数据格式
        nodes = []
        links = []
        node_ids = set()
        
        # 处理每个查询实体的关系
        for entity, data in knowledge_json.items():
            # 确保主实体被添加，但不使用特殊颜色
            if entity not in node_ids:
                # 所有节点使用统一颜色
                nodes.append({
                    "id": entity,
                    "label": entity,
                    "color": "#1976d2"  # 所有节点使用相同的蓝色
                })
                node_ids.add(entity)
            
            # 跳过节点属性处理
            # if "node_properties" in data:
            #     for key, value in data["node_properties"].items():
            #         # 将属性作为节点添加
            #         prop_id = f"{entity}_{key}"
            #         if prop_id not in node_ids:
            #             nodes.append({
            #                 "id": prop_id,
            #                 "label": f"{key}: {value}",
            #                 "color": "#999999"  # 属性节点使用灰色
            #             })
            #             node_ids.add(prop_id)
            #         
            #         # 添加连接
            #         links.append({
            #             "source": entity,
            #             "target": prop_id,
            #             "label": "属性"
            #         })
            
            # 处理关系
            if "relationships" in data:
                for rel in data["relationships"]:
                    source = rel["source"]
                    relation = rel["relation"]
                    target = rel["target"]
                    
                    # 添加源节点
                    if source not in node_ids:
                        nodes.append({
                            "id": source,
                            "label": source,
                            "color": "#1976d2"  # 所有节点使用相同的蓝色
                        })
                        node_ids.add(source)
                    
                    # 添加目标节点
                    if target not in node_ids:
                        nodes.append({
                            "id": target,
                            "label": target,
                            "color": "#1976d2"  # 所有节点使用相同的蓝色
                        })
                        node_ids.add(target)
                    
                    # 添加关系连接
                    links.append({
                        "source": source,
                        "target": target,
                        "label": relation
                    })
                    
                    # 跳过目标节点的属性处理
                    # if "target_properties" in rel:
                    #     for key, value in rel["target_properties"].items():
                    #         # 将属性作为节点添加
                    #         prop_id = f"{target}_{key}"
                    #         if prop_id not in node_ids:
                    #             nodes.append({
                    #                 "id": prop_id,
                    #                 "label": f"{key}: {value}",
                    #                 "color": "#999999"  # 属性节点使用灰色
                    #             })
                    #             node_ids.add(prop_id)
                    #         
                    #         # 添加连接
                    #         links.append({
                    #             "source": target,
                    #             "target": prop_id,
                    #             "label": "属性"
                    #         })
        
        # 对节点进行排序，不再基于类型区分优先级
        # def node_priority(node):
        #     if node["color"] == "#9c27b0":  # 方剂
        #         return 0
        #     elif node["color"] == "#2196f3":  # 中药
        #         return 1
        #     elif node["color"] == "#ff9800":  # 功效/证候/主治
        #         return 2
        #     else:  # 其他
        #         return 3
        # 
        # nodes.sort(key=node_priority)
        
        # 移除限制，返回所有节点和连接
        # max_nodes = 50
        # max_links = 100
        # 
        # if len(nodes) > max_nodes:
        #     nodes = nodes[:max_nodes]
        #     # 确保links中只包含nodes中存在的节点
        #     valid_node_ids = {node["id"] for node in nodes}
        #     links = [link for link in links if link["source"] in valid_node_ids and link["target"] in valid_node_ids]
        # 
        # if len(links) > max_links:
        #     links = links[:max_links]
        
        return jsonify({"nodes": nodes, "links": links})
    
    except Exception as e:
        print("Error generating knowledge graph:", str(e))
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# 重命名对话
@app.route('/api/conversation/<int:conversation_id>/rename', methods=['PUT', 'OPTIONS'])
def rename_conversation(conversation_id):
    if request.method == 'OPTIONS':
        # 处理预检请求
        response = jsonify({"status": "ok"})
        return response

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        new_name = data.get('name')
        user_id = data.get('user_id')

        if not new_name or not new_name.strip():
            return jsonify({'error': '名称不能为空'}), 400

        if not user_id:
            return jsonify({'error': '未登录'}), 401

        print(f"Attempting to rename conversation {conversation_id} for user {user_id} to '{new_name}'")

        with sqlite3.connect('chat_history.db', timeout=20) as conn:
            c = conn.cursor()
            
            # 验证用户是否存在
            c.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if not c.fetchone():
                return jsonify({'error': '用户不存在'}), 404

            # 验证对话是否存在并属于该用户
            c.execute('SELECT user_id FROM conversations WHERE conversation_id = ?', (conversation_id,))
            result = c.fetchone()
            
            if not result:
                return jsonify({'error': '对话不存在'}), 404
                
            if str(result[0]) != str(user_id):
                return jsonify({'error': '无权限修改此对话'}), 403

            # 更新对话名称
            c.execute('UPDATE conversations SET name = ? WHERE conversation_id = ?',
                     (new_name.strip(), conversation_id))
            
            if c.rowcount == 0:
                return jsonify({'error': '更新失败'}), 500

            conn.commit()
            print(f"Successfully renamed conversation {conversation_id}")
            
            return jsonify({
                'status': 'success',
                'message': '重命名成功',
                'conversation_id': conversation_id,
                'new_name': new_name.strip()
            })

    except sqlite3.Error as e:
        print(f"Database error in rename_conversation: {str(e)}")
        return jsonify({'error': f'数据库错误: {str(e)}'}), 500
    except Exception as e:
        print(f"Unexpected error in rename_conversation: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print("Starting server on http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)