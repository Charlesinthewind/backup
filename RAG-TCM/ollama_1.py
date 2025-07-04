# -*- coding: utf-8 -*-
import requests
import json
from typing import List, Dict, Tuple
import re
from deepseek_config import DEEPSEEK_API_KEY, DEEPSEEK_API_BASE

class DeepSeekQuestionProcessor:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.api_base = DEEPSEEK_API_BASE
        
        if self.api_key == "your-api-key-here":
            raise ValueError("请在 deepseek_config.py 文件中设置你的 DeepSeek API key")
    
    def process_question(self, question: str) -> str:
        """Extract entities from the question using DeepSeek API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""你是一名实体抽取专家：

请抽取输入给你语句中的中医相关实体。然后把他们用'/'分割。例如'麻黄汤中中药有哪些,麻黄汤有什么作用，方剂里面有川穹吗。听说麻黄汤主治发烧，还有清热的效果'分割为'麻黄汤/川穹/发烧/清热'，注意！只需要从用户的问题中抽取就行了。一般会显示"用户："。例如：
中的实体就好。我现在给你的是示例。如果提取的是症状。给出近义词比如：“肚子疼怎么办”，提取出‘肚子疼“后，可以再给出肚子疼的同义词。输出例如”萎缩性腹痛/腹痛/肚子疼“等。近义词越多越好。注意，不要提取“归经”，“功效”等这里是用户问题：{question} 
（注意，如果打错字请帮忙纠正），不要有空格或者换行。"""
            
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            response_text = response.json()["choices"][0]["message"]["content"].strip()
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
            return response_text
        except Exception as e:
            print(f"处理问题出错: {str(e)}")
            return question  # 如果处理失败，返回原始问题

def get_questions() -> Tuple[str, str]:
    """获取用户输入并处理问题"""
    print("\n请输入您的中医相关问题：")
    original_question = input().strip()
    
    if not original_question:
        print("输入不能为空")
        return None, None
    
    processor = DeepSeekQuestionProcessor()
    question_for_knowledge = processor.process_question(original_question)
    
    return original_question, question_for_knowledge

if __name__ == "__main__":
    original_question, question_for_knowledge = get_questions()
    if original_question and question_for_knowledge:
        print("\n原始问题：")
        print(original_question)
        print("\n用于知识检索的问题：")
        print(question_for_knowledge) 