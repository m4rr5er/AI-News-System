"""
Database Connectivity Test Script
Tests connections to Redis, MongoDB, and MySQL databases
"""

import sys
from pathlib import Path

# Add backend directory to path for imports
backend_path = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

import redis
import pymongo
import mysql.connector
from datetime import datetime


def test_redis_connection():
    """Test Redis connection"""
    print("\n" + "="*50)
    print("Testing Redis Connection...")
    print("="*50)

    try:
        # Connect to Redis (default: localhost:6379)
        r = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )

        # Test connection with ping
        if r.ping():
            print("✓ Redis connection successful!")

            # Test basic operations
            test_key = f"test_key_{datetime.now().timestamp()}"
            r.set(test_key, "test_value")
            value = r.get(test_key)
            r.delete(test_key)

            print(f"✓ Redis read/write test successful!")
            print(f"  - Server info: {r.info('server')['redis_version']}")

            return True
        else:
            print("✗ Redis ping failed")
            return False

    except redis.ConnectionError as e:
        print(f"✗ Redis connection failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Redis error: {e}")
        return False


def test_mongodb_connection():
    """Test MongoDB connection"""
    print("\n" + "="*50)
    print("Testing MongoDB Connection...")
    print("="*50)

    try:
        # Connect to MongoDB (default: localhost:27017)
        client = pymongo.MongoClient(
            'mongodb://localhost:27017/',
            serverSelectionTimeoutMS=5000
        )

        # Test connection
        client.admin.command('ping')
        print("✓ MongoDB connection successful!")

        # Get server info
        server_info = client.server_info()
        print(f"  - MongoDB version: {server_info['version']}")

        # List databases
        db_list = client.list_database_names()
        print(f"  - Available databases: {', '.join(db_list)}")

        # Test database operations
        test_db = client['test_db']
        test_collection = test_db['test_collection']

        # Insert test document
        test_doc = {
            'test': 'connectivity',
            'timestamp': datetime.now()
        }
        result = test_collection.insert_one(test_doc)

        # Read test document
        found_doc = test_collection.find_one({'_id': result.inserted_id})

        # Delete test document
        test_collection.delete_one({'_id': result.inserted_id})

        print("✓ MongoDB read/write test successful!")

        client.close()
        return True

    except pymongo.errors.ServerSelectionTimeoutError as e:
        print(f"✗ MongoDB connection timeout: {e}")
        return False
    except Exception as e:
        print(f"✗ MongoDB error: {e}")
        return False


def test_mysql_connection():
    """Test MySQL connection"""
    print("\n" + "="*50)
    print("Testing MySQL Connection...")
    print("="*50)

    try:
        # Connect to MySQL
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='123456',
            connection_timeout=5
        )

        if connection.is_connected():
            print("✓ MySQL connection successful!")

            cursor = connection.cursor()

            # Get MySQL version
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"  - MySQL version: {version[0]}")

            # List databases
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            db_names = [db[0] for db in databases]
            print(f"  - Available databases: {', '.join(db_names)}")

            # Test database operations
            cursor.execute("CREATE DATABASE IF NOT EXISTS test_db")
            cursor.execute("USE test_db")

            # Create test table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    test_data VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert test data
            cursor.execute(
                "INSERT INTO test_table (test_data) VALUES (%s)",
                ("connectivity_test",)
            )
            connection.commit()

            # Read test data
            cursor.execute("SELECT * FROM test_table WHERE test_data = %s", ("connectivity_test",))
            result = cursor.fetchone()

            # Clean up
            cursor.execute("DROP TABLE test_table")
            cursor.execute("DROP DATABASE test_db")
            connection.commit()

            print("✓ MySQL read/write test successful!")

            cursor.close()
            connection.close()
            return True
        else:
            print("✗ MySQL connection failed")
            return False

    except mysql.connector.Error as e:
        print(f"✗ MySQL error: {e}")
        return False
    except Exception as e:
        print(f"✗ MySQL unexpected error: {e}")
        return False


def main():
    """Run all database connectivity tests"""
    print("\n" + "="*50)
    print("DATABASE CONNECTIVITY TEST")
    print("="*50)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        'Redis': test_redis_connection(),
        'MongoDB': test_mongodb_connection(),
        'MySQL': test_mysql_connection()
    }

    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)

    for db_name, status in results.items():
        status_icon = "✓" if status else "✗"
        status_text = "PASSED" if status else "FAILED"
        print(f"{status_icon} {db_name}: {status_text}")

    all_passed = all(results.values())
    print("\n" + "="*50)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*50)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
