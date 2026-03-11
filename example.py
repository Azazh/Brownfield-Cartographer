import pandas as pd
from sqlalchemy import create_engine
from pyspark.sql import SparkSession

# Pandas
users = pd.read_csv('data/users.csv')
orders = pd.read_sql('SELECT * FROM orders', con='sqlite:///orders.db')

# SQLAlchemy
engine = create_engine('sqlite:///orders.db')
result = engine.execute('SELECT * FROM orders')

# PySpark
spark = SparkSession.builder.appName('Demo').getOrCreate()
df = spark.read.csv('data/orders.csv')
df.write.parquet('output/orders.parquet')
