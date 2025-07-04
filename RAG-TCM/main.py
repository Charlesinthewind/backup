# -*- coding: utf-8 -*-
from ollama_1 import get_questions
from get_knowledge import get_knowledge
from ollama_2 import get_answer
import json
import os

def main(original_question=None, question_for_knowledge=None):
    print("开始执行中医知识问答流程...")
    
    # 1. 如果没有提供问题，则从用户输入获取
    if original_question is None or question_for_knowledge is None:
        original_question, question_for_knowledge = get_questions()
        if not original_question or not question_for_knowledge:
            print("获取问题失败，程序终止")
            return "获取问题失败"
    
    print("\n用于知识检索的问题：")
    print(question_for_knowledge)

    # 2. 获取相关知识
    print("\n=== 第二步：检索知识 ===")
    get_knowledge(question_for_knowledge)
    
    try:
        with open('query_results.json', 'r', encoding='utf-8') as f:
            knowledge = json.load(f)
    except FileNotFoundError:
        print("获取知识失败，找不到query_results.json文件")
        return "获取知识失败"
    except json.JSONDecodeError:
        print("获取知识失败，query_results.json文件格式错误")
        return "获取知识失败"
    
    if not knowledge:
        print("获取知识失败，没有找到相关知识")
        return "获取知识失败"

    # 3. 生成回答（使用带有上下文的原始问题）
    print("\n=== 第三步：生成回答 ===")
    answer = get_answer(original_question, knowledge)
    print("\n回答：")
    print(answer)
    
    print("\n流程执行完成！")
    return answer

if __name__ == "__main__":
    main() 