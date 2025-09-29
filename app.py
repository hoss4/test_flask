import os
import psycopg2
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Database configuration
def get_db_connection():
    # Railway sets DATABASE_URL environment variable
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        return None, "DATABASE_URL environment variable not set"
    
    try:
        # Railway uses postgres://, but newer versions need postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        conn = psycopg2.connect(database_url)
        return conn, None
    except Exception as e:
        return None, f"Connection error: {str(e)}"

def init_db():
    """Create a test table if it doesn't exist"""
    conn, error = get_db_connection()
    if error:
        return error
    
    try:
        with conn.cursor() as cur:
            # Create a simple test table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_messages (
                    id SERIAL PRIMARY KEY,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Insert a test message if table is empty
            cur.execute("SELECT COUNT(*) FROM test_messages")
            count = cur.fetchone()[0]
            
            if count == 0:
                cur.execute(
                    "INSERT INTO test_messages (message) VALUES (%s)",
                    ("Hello from Railway PostgreSQL!",)
                )
            
            conn.commit()
        return None
    except Exception as e:
        return f"Init DB error: {str(e)}"
    finally:
        conn.close()

@app.route('/')
def index():
    """Main page showing database status"""
    conn, conn_error = get_db_connection()
    
    if conn_error:
        return render_template('index.html', 
                             connected=False, 
                             error=conn_error,
                             messages=[])
    
    try:
        # Try to fetch some data
        with conn.cursor() as cur:
            cur.execute("SELECT id, message, created_at FROM test_messages ORDER BY created_at DESC")
            messages = cur.fetchall()
        
        return render_template('index.html', 
                             connected=True, 
                             error=None,
                             messages=messages)
    except Exception as e:
        return render_template('index.html', 
                             connected=False, 
                             error=f"Query error: {str(e)}",
                             messages=[])
    finally:
        conn.close()

@app.route('/add-message', methods=['POST'])
def add_message():
    """Add a new message to the database"""
    message = request.form.get('message', 'Test message')
    
    conn, conn_error = get_db_connection()
    if conn_error:
        return jsonify({'success': False, 'error': conn_error})
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO test_messages (message) VALUES (%s) RETURNING id, created_at",
                (message,)
            )
            result = cur.fetchone()
            conn.commit()
        
        return jsonify({
            'success': True, 
            'id': result[0], 
            'created_at': result[1].isoformat(),
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    conn, error = get_db_connection()
    if error:
        return jsonify({'status': 'error', 'database': 'disconnected', 'error': error})
    
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'database': 'error', 'error': str(e)})

# Initialize database when app starts
@app.before_first_request
def initialize():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)