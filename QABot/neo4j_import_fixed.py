# neo4j_import_fixed.py
"""
Neo4j数据库数据导入脚本 - 修复版
专门处理GBK编码的CSV文件，确保中文字符正确导入到Neo4j数据库中
"""

import os
import csv
import logging
from py2neo import Graph
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('neo4j_import_fixed.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Neo4jImporterFixed:
    """Neo4j数据导入器 - 修复版，专门处理GBK编码"""

    def __init__(self, database_name="doctorss"):
        """初始化Neo4j连接"""
        try:
            self.database_name = database_name
            self.graph = Graph(
                os.getenv('NEO4J_URI'),
                auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
                name=database_name
            )
            # 测试连接
            result = self.graph.run("CALL dbms.components() YIELD versions, name RETURN name, versions[0] as version").data()
            if result:
                logger.info(f"✅ Neo4j连接成功！数据库：{database_name}，Neo4j版本：{result[0]['name']} {result[0]['version']}")
            else:
                raise Exception("无法获取数据库信息")
        except Exception as e:
            logger.error(f"❌ Neo4j连接失败：{str(e)}")
            raise

    def read_csv_with_proper_encoding(self, file_path):
        """使用正确的编码读取CSV文件"""
        # 首先尝试UTF-8
        encodings_to_try = ['utf-8', 'gbk', 'gb2312']

        for encoding in encodings_to_try:
            try:
                # 先读取文件头检测是否为BOM
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    # 检测BOM
                    if raw_data.startswith(b'\xef\xbb\xbf'):  # UTF-8 BOM
                        encoding = 'utf-8-sig'
                        raw_data = raw_data[3:]

                # 使用检测到的编码读取
                content = raw_data.decode(encoding)
                reader = csv.DictReader(content.splitlines())
                return reader, encoding

            except (UnicodeDecodeError, UnicodeError):
                continue

        raise UnicodeDecodeError(f"无法读取文件：{file_path}")

    def create_nodes(self):
        """创建节点 - 修复版"""
        logger.info("开始创建节点...")

        # 节点类型配置
        node_configs = {
            'Category': {'file': 'Category.csv', 'properties': ['name']},
            'Check': {'file': 'Check.csv', 'properties': ['name']},
            'Cureway': {'file': 'Cureway.csv', 'properties': ['name']},
            'Department': {'file': 'Department.csv', 'properties': ['name']},
            'Disease': {
                'file': 'Disease.csv',
                'properties': ['name', 'desc', 'prevent', 'cause', 'yibao_status',
                             'get_prob', 'get_way', 'cure_lasttime', 'cured_prob', 'cost_money']
            },
            'Dishes': {'file': 'Dishes.csv', 'properties': ['name']},
            'Drug': {'file': 'Drug.csv', 'properties': ['name']},
            'Food': {'file': 'Food.csv', 'properties': ['name']},
            'Symptom': {'file': 'Symptom.csv', 'properties': ['name']}
        }

        nodes_path = os.path.join(os.path.dirname(__file__), 'doctor', 'nodes')

        for node_type, config in node_configs.items():
            file_path = os.path.join(nodes_path, config['file'])
            if not os.path.exists(file_path):
                logger.warning(f"文件不存在：{file_path}")
                continue

            logger.info(f"正在导入{node_type}节点...")

            try:
                # 读取CSV文件
                reader, encoding = self.read_csv_with_proper_encoding(file_path)
                logger.info(f"成功以{encoding}编码读取文件：{config['file']}")

                count = 0
                for row in reader:
                    # 构建节点属性，确保所有值都是字符串类型
                    properties = {}
                    for prop in config['properties']:
                        value = row.get(prop, '').strip()
                        if value:  # 只添加非空值
                            properties[prop] = str(value)

                    if not properties:
                        continue

                    # 构建Cypher查询
                    props_str = ', '.join([f"{k}: ${k}" for k in properties.keys()])
                    query = f"CREATE (:{node_type} {{{props_str}}})"

                    try:
                        self.graph.run(query, **properties)
                        count += 1
                    except Exception as e:
                        logger.error(f"创建{node_type}节点失败：{properties}，错误：{str(e)}")
                        # 记录更详细的错误信息
                        logger.error(f"失败的查询：{query}")

                logger.info(f"✅ {node_type}节点导入完成，共导入{count}个节点")

            except Exception as e:
                logger.error(f"导入{node_type}节点时出错：{str(e)}")
                # 记录堆栈跟踪
                import traceback
                logger.error(traceback.format_exc())

    def create_indexes(self):
        """创建索引"""
        logger.info("开始创建索引...")

        index_configs = [
            'Category', 'Check', 'Cureway', 'Department',
            'Disease', 'Dishes', 'Drug', 'Food', 'Symptom'
        ]

        for node_type in index_configs:
            try:
                query = f"CREATE INDEX IF NOT EXISTS FOR (n:{node_type}) ON (n.name)"
                self.graph.run(query)
                logger.info(f"✅ 为{node_type}创建name属性索引成功")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"索引已存在：{node_type}.name")
                else:
                    logger.warning(f"为{node_type}创建索引失败：{str(e)}")

    def create_relationships(self):
        """创建关系 - 修复版"""
        logger.info("开始创建关系...")

        # 关系类型配置
        relationship_configs = {
            'DISEASE_ACOMPANY': {'from_type': 'Disease', 'to_type': 'Disease', 'file': 'DISEASE_ACOMPANY.csv'},
            'DISEASE_CATEGORY': {'from_type': 'Disease', 'to_type': 'Category', 'file': 'DISEASE_CATEGORY.csv'},
            'DISEASE_CHECK': {'from_type': 'Disease', 'to_type': 'Check', 'file': 'DISEASE_CHECK.csv'},
            'DISEASE_CUREWAY': {'from_type': 'Disease', 'to_type': 'Cureway', 'file': 'DISEASE_CUREWAY.csv'},
            'DISEASE_DEPARTMENT': {'from_type': 'Disease', 'to_type': 'Department', 'file': 'DISEASE_DEPARTMENT.csv'},
            'DISEASE_DISHES': {'from_type': 'Disease', 'to_type': 'Dishes', 'file': 'DISEASE_DISHES.csv'},
            'DISEASE_DO_EAT': {'from_type': 'Disease', 'to_type': 'Food', 'file': 'DISEASE_DO_EAT.csv'},
            'DISEASE_DRUG': {'from_type': 'Disease', 'to_type': 'Drug', 'file': 'DISEASE_DRUG.csv'},
            'DISEASE_NOT_EAT': {'from_type': 'Disease', 'to_type': 'Food', 'file': 'DISEASE_NOT_EAT.csv'},
            'DISEASE_SYMPTOM': {'from_type': 'Disease', 'to_type': 'Symptom', 'file': 'DISEASE_SYMPTOM.csv'}
        }

        relations_path = os.path.join(os.path.dirname(__file__), 'doctor', 'relations')

        for rel_type, config in relationship_configs.items():
            file_path = os.path.join(relations_path, config['file'])
            if not os.path.exists(file_path):
                logger.warning(f"文件不存在：{file_path}")
                continue

            logger.info(f"正在导入{rel_type}关系...")

            try:
                # 读取CSV文件
                reader, encoding = self.read_csv_with_proper_encoding(file_path)
                logger.info(f"成功以{encoding}编码读取文件：{config['file']}")

                count = 0
                for row in reader:
                    from_name = row.get('from', '').strip()
                    to_name = row.get('to', '').strip()

                    if not from_name or not to_name:
                        continue

                    # 确保名称是字符串类型
                    from_name = str(from_name)
                    to_name = str(to_name)

                    # 构建Cypher查询
                    query = f"""
                    MATCH (from:{config['from_type']} {{name: $from_name}})
                    MATCH (to:{config['to_type']} {{name: $to_name}})
                    MERGE (from)-[:{rel_type}]->(to)
                    """

                    try:
                        self.graph.run(query, from_name=from_name, to_name=to_name)
                        count += 1
                    except Exception as e:
                        logger.error(f"创建{rel_type}关系失败：{from_name} -> {to_name}，错误：{str(e)}")

                logger.info(f"✅ {rel_type}关系导入完成，共导入{count}个关系")

            except Exception as e:
                logger.error(f"导入{rel_type}关系时出错：{str(e)}")
                import traceback
                logger.error(traceback.format_exc())

    def clear_database(self):
        """清空数据库（慎用）"""
        logger.warning("正在清空数据库...")
        try:
            self.graph.run("MATCH (n) DETACH DELETE n")
            logger.info("✅ 数据库已清空")
        except Exception as e:
            logger.error(f"清空数据库失败：{str(e)}")

    def test_encoding(self):
        """测试编码处理是否正确"""
        logger.info("开始测试编码处理...")

        try:
            # 创建一个测试节点
            test_query = "CREATE (:TestEncoding {name: $name, desc: $desc})"
            test_data = {
                'name': '测试疾病',
                'desc': '这是一个编码测试，包含中文字符：肺炎、咳嗽、发热等症状。'
            }

            self.graph.run(test_query, **test_data)

            # 查询测试数据
            result = self.graph.run("MATCH (n:TestEncoding) RETURN n.name AS name, n.desc AS desc").data()

            if result:
                logger.info("✅ 编码测试成功！")
                logger.info(f"测试数据：{result[0]}")

                # 检查中文字符是否正确显示
                if '测试疾病' in result[0]['name'] and '肺炎' in result[0]['desc']:
                    logger.info("✅ 中文字符显示正确！")
                else:
                    logger.warning("⚠️ 中文字符可能有问题")

            # 清理测试数据
            self.graph.run("MATCH (n:TestEncoding) DELETE n")
            logger.info("测试数据已清理")

        except Exception as e:
            logger.error(f"编码测试失败：{str(e)}")

    def run_import(self, clear_db=False, test_encoding=True):
        """执行完整的导入流程"""
        logger.info("开始执行Neo4j数据导入...")

        if test_encoding:
            self.test_encoding()

        if clear_db:
            self.clear_database()

        try:
            # 创建节点
            self.create_nodes()

            # 创建索引
            self.create_indexes()

            # 创建关系
            self.create_relationships()

            logger.info("✅ 数据导入完成！")

        except Exception as e:
            logger.error(f"数据导入过程中出现错误：{str(e)}")
            raise


def main():
    """主函数"""
    try:
        # 使用doctorss数据库
        importer = Neo4jImporterFixed(database_name="doctorss")
        # 注意：clear_db=True会清空数据库，请谨慎使用
        importer.run_import(clear_db=True, test_encoding=True)
    except Exception as e:
        logger.error(f"程序执行失败：{str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
