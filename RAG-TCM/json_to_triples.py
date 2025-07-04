#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os

def json_to_triples(json_file, output_file=None):
    """
    将JSON格式的知识图谱查询结果转换为三元组形式
    
    参数:
    json_file: JSON文件路径
    output_file: 输出文件路径，如果为None则只返回三元组而不保存
    
    返回:
    list: 三元组列表，每个三元组为(source, relation, target)
    """
    # 读取JSON文件
    with open(json_file, 'r', encoding='utf-8') as f:
        knowledge_json = json.load(f)
    
    # 存储所有三元组
    triples = []
    
    # 遍历每个查询实体
    for entity, data in knowledge_json.items():
        # 处理节点属性
        if "node_properties" in data:
            for key, value in data["node_properties"].items():
                triple = (entity, key, str(value))
                if triple not in triples:
                    triples.append(triple)
        
        # 处理关系
        if "relationships" in data:
            for rel in data["relationships"]:
                source = rel["source"]
                relation = rel["relation"]
                target = rel["target"]
                
                # 添加基本关系三元组
                triple = (source, relation, target)
                if triple not in triples:
                    triples.append(triple)
                
                # 处理目标节点的属性
                if "target_properties" in rel:
                    for key, value in rel["target_properties"].items():
                        prop_triple = (target, key, str(value))
                        if prop_triple not in triples:
                            triples.append(prop_triple)
    
    # 保存到文件(如果指定了输出文件)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            for s, p, o in triples:
                f.write(f"{s}\t{p}\t{o}\n")
        print(f"已将三元组保存到 {output_file}，共 {len(triples)} 条")
    
    return triples

def print_triples(triples, limit=None):
    """打印三元组"""
    count = min(limit, len(triples)) if limit else len(triples)
    print(f"共有 {len(triples)} 条三元组，显示前 {count} 条:")
    
    for i, (s, p, o) in enumerate(triples[:count]):
        print(f"{i+1}. {s} -- {p} --> {o}")

if __name__ == "__main__":
    # 检查输入文件是否存在
    json_file = "query_results.json"
    if not os.path.exists(json_file):
        print(f"错误: 文件 {json_file} 不存在")
        exit(1)
    
    # 设置输出文件
    output_file = "query_results_triples.txt"
    
    # 转换并保存
    triples = json_to_triples(json_file, output_file)
    
    # 打印前20条三元组示例
    print_triples(triples, 20) 