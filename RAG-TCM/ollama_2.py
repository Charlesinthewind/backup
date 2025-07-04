# -*- coding: utf-8 -*-
import requests
import json
import re
import sys
import asyncio
import aiohttp
from deepseek_config import DEEPSEEK_API_KEY, DEEPSEEK_API_BASE

class DeepSeekAnswerGenerator:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.api_base = DEEPSEEK_API_BASE
        self.max_chunks_per_batch = 6  # 每批处理的chunk数量
        self.max_chunk_size = 6000  # 每个chunk的最大字符数
        self.max_context_length = 40000  # 对话上下文的最大字符数（约1万tokens）
        self.max_parallel_requests = 3  # 最大并行请求数
#         self.max_chunks_per_batch = 4
# self.max_chunk_size = 4500
# self.max_context_length = 30000

        # self.max_chunks_per_batch = 2  # 减少每批处理的chunk数量
        # self.max_chunk_size = 1500  # 每个chunk的最大字符数
        # self.max_context_length = 6000  # 对话上下文的最大字符数
        if self.api_key == "your-api-key-here":
            raise ValueError("请在 deepseek_config.py 文件中设置你的 DeepSeek API key")
    
    def format_knowledge(self, knowledge_json: dict) -> str:
        """将JSON格式的知识转换为文本格式"""
        formatted_text = []
        
        for entity, data in knowledge_json.items():
            formatted_text.append(f"实体：{entity}")
            
            # 添加节点属性（如果有）
            if "node_properties" in data:
                formatted_text.append("属性：")
                for key, value in data["node_properties"].items():
                    formatted_text.append(f"- {key}: {value}")
            
            # 添加关系信息
            if "relationships" in data:
                formatted_text.append("关系：")
                for rel in data["relationships"]:
                    relation_text = f"- {rel['source']} {rel['relation']} {rel['target']}"
                    if "target_properties" in rel:
                        props = [f"{k}: {v}" for k, v in rel["target_properties"].items()]
                        if props:
                            relation_text += f" ({'; '.join(props)})"
                    formatted_text.append(relation_text)
            
            formatted_text.append("")  # 添加空行分隔不同实体
        
        return "\n".join(formatted_text)

    def truncate_text(self, text: str, max_length: int) -> str:
        """截断文本到指定长度，保持完整的句子"""
        if len(text) <= max_length:
            return text
        
        # 在最大长度位置查找最后一个完整句子
        truncated = text[:max_length]
        last_period = max(
            truncated.rfind('。'),
            truncated.rfind('！'),
            truncated.rfind('？'),
            truncated.rfind('\n')
        )
        
        if last_period != -1:
            return text[:last_period + 1]
        return text[:max_length] + "..."

    def split_knowledge_by_entities(self, knowledge_json: dict) -> list:
        """将知识库按实体分割成多个小块"""
        knowledge_chunks = []
        current_chunk = {}
        current_size = 0
        
        for entity, data in knowledge_json.items():
            # 估算当前实体的大小
            entity_data = {entity: data}
            entity_text = self.format_knowledge(entity_data)
            entity_size = len(entity_text)
            
            # 如果当前实体太大，需要单独处理
            if entity_size > self.max_chunk_size:
                if current_chunk:  # 先保存当前chunk
                    knowledge_chunks.append(self.format_knowledge(current_chunk))
                    current_chunk = {}
                    current_size = 0
                
                # 将大实体的文本截断并分成多个chunk
                truncated_text = self.truncate_text(entity_text, self.max_chunk_size)
                knowledge_chunks.append(truncated_text)
                continue
            
            # 如果当前chunk为空或者加入新实体后不会太大，则添加到当前chunk
            if current_size == 0 or current_size + entity_size <= self.max_chunk_size:
                current_chunk.update(entity_data)
                current_size += entity_size
            else:
                # 当前chunk已满，保存并创建新的chunk
                knowledge_chunks.append(self.format_knowledge(current_chunk))
                current_chunk = entity_data
                current_size = entity_size
        
        # 添加最后一个chunk
        if current_chunk:
            knowledge_chunks.append(self.format_knowledge(current_chunk))
        
        return knowledge_chunks

    def get_total_length(self, messages: list) -> int:
        """计算消息列表的总字符数"""
        return sum(len(str(m.get("content", ""))) for m in messages)

    async def process_chunk_async(self, session, messages, batch_text, batch_index):
        """异步处理单个知识块"""
        try:
            # 添加当前批次的知识到消息列表
            current_messages = messages.copy()
            current_messages.append({
                "role": "user",
                "content": f"这是第{batch_index + 1}批知识：\n\n{batch_text}"
            })

            # 发送API请求
            async with session.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": current_messages,
                    "temperature": 0.1,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                full_response = ""
                
                # 处理流式响应
                async for line in response.content:
                    try:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            json_str = line[6:]
                            if json_str == '[DONE]':
                                break
                            chunk = json.loads(json_str)
                            if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                                content = chunk['choices'][0]['delta']['content']
                                full_response += content
                    except json.JSONDecodeError:
                        continue

                return {
                    "batch_index": batch_index,
                    "response": full_response
                }

        except Exception as e:
            print(f"\n处理第{batch_index + 1}批知识时出错: {str(e)}")
            return {
                "batch_index": batch_index,
                "error": str(e)
            }

    async def process_chunks_parallel(self, chunks, question):
        """并行处理多个知识块"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一个中医知识问答助手。你需要基于提供的知识回答问题。请记住所有提供的知识，并在最后给出完整的回答。"
                },
                {
                    "role": "user",
                    "content": f"问题是：{question}\n\n我会分多次提供知识库内容，请你记住这些知识，最后回答问题。"
                },
                {
                    "role": "assistant",
                    "content": "好的，我会仔细阅读每部分知识，并在最后给出完整的回答。请提供第一部分知识。"
                }
            ]

            # 创建异步会话
            async with aiohttp.ClientSession() as session:
                # 分批处理chunks
                all_responses = []
                for i in range(0, len(chunks), self.max_chunks_per_batch):
                    batch_tasks = []
                    current_batch = chunks[i:i + self.max_chunks_per_batch]
                    
                    # 创建当前批次的所有任务
                    for j, chunk in enumerate(current_batch):
                        if len(chunk) > self.max_chunk_size:
                            chunk = self.truncate_text(chunk, self.max_chunk_size)
                        
                        batch_index = i + j
                        task = self.process_chunk_async(session, messages, chunk, batch_index)
                        batch_tasks.append(task)
                    
                    # 使用信号量限制并发请求数
                    semaphore = asyncio.Semaphore(self.max_parallel_requests)
                    async def process_with_semaphore(task):
                        async with semaphore:
                            return await task
                    
                    # 并行执行当前批次的任务
                    batch_responses = await asyncio.gather(
                        *(process_with_semaphore(task) for task in batch_tasks)
                    )
                    
                    # 处理响应
                    for response in batch_responses:
                        if "error" not in response:
                            messages.append({
                                "role": "assistant",
                                "content": response["response"]
                            })
                            all_responses.append(response)
                
                # 请求最终答案
                final_prompt = f"现在你已经看完了所有知识，请基于这些知识回答最初的问题：{question}\n\n请给出准确、简洁的回答，如果一个方剂在多本书中出现，请综合回答，告诉我们出自哪本书。但不要自己添加自己查询的信息（如果没有对应书籍就不要写书籍了，直接写结果）。"
                
                # 确保最终请求不会太长
                while self.get_total_length(messages) + len(final_prompt) > self.max_context_length:
                    for j in range(1, len(messages)):
                        if messages[j]["role"] != "system":
                            messages.pop(j)
                            break
                
                messages.append({
                    "role": "user",
                    "content": final_prompt
                })
                
                # 获取最终答案
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": messages,
                        "temperature": 0.1,
                        "stream": True
                    }
                ) as response:
                    response.raise_for_status()
                    final_response = ""
                    
                    async for line in response.content:
                        try:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                json_str = line[6:]
                                if json_str == '[DONE]':
                                    break
                                chunk = json.loads(json_str)
                                if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                                    content = chunk['choices'][0]['delta']['content']
                                    print(content, end='', flush=True)
                                    final_response += content
                        except json.JSONDecodeError:
                            continue
                    
                    print()  # 最后换行
                    return final_response

        except Exception as e:
            return f"处理知识块时出错: {str(e)}"

    def generate_answer(self, knowledge_json: dict, question: str) -> str:
        """基于JSON格式的知识库和问题生成回答"""
        try:
            # 将知识库分割成多个小块
            knowledge_chunks = self.split_knowledge_by_entities(knowledge_json)
            
            if not knowledge_chunks:
                return "知识库为空，无法回答问题"
            
            # 使用异步方式处理所有chunks
            return asyncio.run(self.process_chunks_parallel(knowledge_chunks, question))
            
        except Exception as e:
            return f"生成回答出错: {str(e)}"

def get_answer(question: str, knowledge_json: dict) -> str:
    """生成回答"""
    generator = DeepSeekAnswerGenerator()
    return generator.generate_answer(knowledge_json, question)

if __name__ == "__main__":
    # 从文件读取输入（仅用于独立运行）
    try:
        with open('query_results.json', 'r', encoding='utf-8') as f:
            knowledge = json.load(f)
        
        print("请输入您的问题：")
        question = input().strip()
        
        answer = get_answer(question, knowledge)
        print("\n回答：")
        print(answer)
        
    except Exception as e:
        print(f"处理出错: {str(e)}") 