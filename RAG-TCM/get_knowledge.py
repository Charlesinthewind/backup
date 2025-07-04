# -*- coding: utf-8 -*-
from neo4j import GraphDatabase
import json

class Neo4jQuerier:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def check_entity_exists(self, entity_name):
        """检查实体是否存在于数据库中"""
        with self.driver.session() as session:
            query = """
            MATCH (n)
            WHERE n.name IS NOT NULL AND n.name CONTAINS $entity_name
            RETURN count(n) > 0 as exists
            """
            result = session.run(query, entity_name=entity_name)
            return result.single()["exists"]

    def query_related_nodes(self, x):
        with self.driver.session() as session:
            # 第一跳查询
            query = """
            MATCH (n)-[r]-(m)
            WHERE n.name CONTAINS $node_name
            RETURN n, type(r) as relation_type, m, labels(n) as source_labels, labels(m) as target_labels
            """
            result = session.run(query, node_name=x)
            
            # 创建结果字典
            result_dict = {
                "query_node": x,
                "relationships": []
            }
            
            # 用于存储查询节点的属性（如果是中药）
            first_record = None
            second_hop_nodes = []  # 存储需要进行二跳查询的节点
            # formula_nodes = []  # 移除方剂节点收集，不再进行1.5跳查询
            
            # 处理第一跳结果
            for record in result:
                if first_record is None:
                    first_record = record
                
                source = record["n"]
                relation = record["relation_type"]
                target = record["m"]
                source_labels = record["source_labels"]
                target_labels = record["target_labels"]
                
                source_name = dict(source).get('name', 'Unknown')
                target_name = dict(target).get('name', 'Unknown')
                
                relationship = {
                    "source": source_name,
                    "relation": relation,
                    "target": target_name,
                    "target_labels": target_labels,
                    "hop": 1
                }
                
                # 处理中药属性
                if "中药" in target_labels:
                    properties = dict(target)
                    if "方剂" in source_labels:
                        herb_properties = {
                            k: v for k, v in properties.items() 
                            if k != 'name' and source_name in k
                        }
                    else:
                        herb_properties = {
                            k: v for k, v in properties.items() 
                            if k != 'name'
                        }
                    if herb_properties:
                        relationship["target_properties"] = herb_properties
                
                result_dict["relationships"].append(relationship)

                # 收集同义词节点进行二跳查询
                if relation == "同义词":
                    second_hop_nodes.append(target_name)
                
                # 移除方剂节点的收集部分
                # if "方剂" in target_labels:
                #     formula_nodes.append(target_name)
            
            # 移除整个1.5跳的处理逻辑
            # 处理第一跳发现的方剂节点
            # for formula in formula_nodes:
            #     query = """
            #     MATCH (n)-[r]-(m)
            #     WHERE n.name = $node_name
            #     RETURN n, type(r) as relation_type, m, labels(n) as source_labels, labels(m) as target_labels
            #     """
            #     formula_result = session.run(query, node_name=formula)
            #     
            #     for record in formula_result:
            #         source = record["n"]
            #         relation = record["relation_type"]
            #         target = record["m"]
            #         source_labels = record["source_labels"]
            #         target_labels = record["target_labels"]
            #         
            #         source_name = dict(source).get('name', 'Unknown')
            #         target_name = dict(target).get('name', 'Unknown')
            #         
            #         relationship = {
            #             "source": source_name,
            #             "relation": relation,
            #             "target": target_name,
            #             "target_labels": target_labels,
            #             "from_formula": formula,  # 记录是从哪个方剂扩展出来的
            #             "hop": 1.5  # 使用1.5表示是第一跳方剂的关联信息
            #         }
            #         
            #         # 处理中药属性
            #         if "中药" in target_labels:
            #             properties = dict(target)
            #             if "方剂" in source_labels:
            #                 herb_properties = {
            #                     k: v for k, v in properties.items() 
            #                     if k != 'name' and source_name in k
            #                 }
            #             else:
            #                 herb_properties = {
            #                     k: v for k, v in properties.items() 
            #                     if k != 'name'
            #                 }
            #             if herb_properties:
            #                 relationship["target_properties"] = herb_properties
            #         
            #         result_dict["relationships"].append(relationship)

            # 第二跳查询（同义词）
            third_hop_nodes = []  # 存储需要进行三跳查询的节点
            for node in second_hop_nodes:
                query = """
                MATCH (n)-[r]-(m)
                WHERE n.name = $node_name AND type(r) = '同义词'
                RETURN n, type(r) as relation_type, m, labels(n) as source_labels, labels(m) as target_labels
                """
                second_hop_result = session.run(query, node_name=node)
                
                for record in second_hop_result:
                    source = record["n"]
                    relation = record["relation_type"]
                    target = record["m"]
                    target_labels = record["target_labels"]
                    
                    source_name = dict(source).get('name', 'Unknown')
                    target_name = dict(target).get('name', 'Unknown')
                    
                    relationship = {
                        "source": source_name,
                        "relation": relation,
                        "target": target_name,
                        "via_synonym": node,
                        "target_labels": target_labels,
                        "hop": 2
                    }
                    
                    result_dict["relationships"].append(relationship)
                    third_hop_nodes.append(target_name)
            
            # 第三跳查询（查找方剂）
            fourth_hop_nodes = []  # 存储需要进行四跳查询的方剂节点
            for node in third_hop_nodes:
                query = """
                MATCH (n)-[r]-(m:方剂)
                WHERE n.name = $node_name AND type(r) = '主治'
                RETURN n, type(r) as relation_type, m, labels(n) as source_labels, labels(m) as target_labels
                """
                third_hop_result = session.run(query, node_name=node)
                
                for record in third_hop_result:
                    source = record["n"]
                    relation = record["relation_type"]
                    target = record["m"]
                    target_labels = record["target_labels"]
                    
                    source_name = dict(source).get('name', 'Unknown')
                    target_name = dict(target).get('name', 'Unknown')
                    
                    relationship = {
                        "source": source_name,
                        "relation": relation,
                        "target": target_name,
                        "target_labels": target_labels,
                        "hop": 3
                    }
                    
                    result_dict["relationships"].append(relationship)
                    fourth_hop_nodes.append(target_name)
            
            # 第四跳查询（方剂的所有相关节点）
            for formula in fourth_hop_nodes:
                query = """
                MATCH (n)-[r]-(m)
                WHERE n.name = $node_name
                RETURN n, type(r) as relation_type, m, labels(n) as source_labels, labels(m) as target_labels
                """
                fourth_hop_result = session.run(query, node_name=formula)
                
                for record in fourth_hop_result:
                    source = record["n"]
                    relation = record["relation_type"]
                    target = record["m"]
                    source_labels = record["source_labels"]
                    target_labels = record["target_labels"]
                    
                    source_name = dict(source).get('name', 'Unknown')
                    target_name = dict(target).get('name', 'Unknown')
                    
                    relationship = {
                        "source": source_name,
                        "relation": relation,
                        "target": target_name,
                        "target_labels": target_labels,
                        "from_formula": formula,  # 记录是从哪个方剂扩展出来的
                        "hop": 4
                    }
                    
                    # 处理中药属性
                    if "中药" in target_labels:
                        properties = dict(target)
                        if "方剂" in source_labels:
                            herb_properties = {
                                k: v for k, v in properties.items() 
                                if k != 'name' and source_name in k
                            }
                        else:
                            herb_properties = {
                                k: v for k, v in properties.items() 
                                if k != 'name'
                            }
                        if herb_properties:
                            relationship["target_properties"] = herb_properties
                    
                    result_dict["relationships"].append(relationship)
            
            # 如果查询节点本身是中药，添加其属性
            if first_record and "中药" in first_record["source_labels"]:
                source_properties = dict(first_record["n"])
                herb_properties = {
                    k: v for k, v in source_properties.items() 
                    if k != 'name'
                }
                if herb_properties:
                    result_dict["node_properties"] = herb_properties
            
            return result_dict if result_dict["relationships"] else None

def get_knowledge(question):
    # Neo4j连接配置
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "zhao20030401zcq"

    try:
        querier = Neo4jQuerier(uri, user, password)
        
        # 获取用户输入并分割
        entities = [e.strip() for e in question.split('/') if e.strip()]
        
        # 存储所有有效查询结果
        valid_results = {}
        
        # 查询每个实体
        for entity in entities:
            # 检查实体是否存在
            if querier.check_entity_exists(entity):
                result = querier.query_related_nodes(entity)
                if result:  # 只有当查询结果不为空时才添加
                    valid_results[entity] = result
        
        # 如果有有效结果，输出并保存
        if valid_results:
            print(json.dumps(valid_results, ensure_ascii=False, indent=2))
            # 保存结果到文件
            with open('query_results.json', 'w', encoding='utf-8') as f:
                json.dump(valid_results, f, ensure_ascii=False, indent=2)
        
    except Exception as e:
        print(f"查询出错: {str(e)}")
    
    finally:
        if 'querier' in locals():
            querier.close()

