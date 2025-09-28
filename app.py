import io
import json
import base64
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Initialize the Flask application
app = Flask(__name__)
# Set a configuration for uploaded file size (optional, but good practice)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB limit

# Define the data conversion logic
def convert_data(input_data, input_format, output_format):
    """
    Reads input data into a Pandas DataFrame and converts it to the desired output format.
    Input data can be a file stream or a string.
    """
    df = None
    try:
        # --- STEP 1: Read Input Data into a Pandas DataFrame ---

        if input_format == 'csv':
            # Use io.StringIO to treat the string/file stream as a file-like object
            if isinstance(input_data, str):
                df = pd.read_csv(io.StringIO(input_data))
            else:
                df = pd.read_csv(input_data)

        elif input_format == 'json':
            # Attempt to read JSON. Assuming the input is a string for simplicity (pasted or read file content)
            # We'll use the 'lines=True' argument for json lines format support, which is common.
            # If a file is uploaded, the stream is read as bytes, so we decode it.
            json_string = input_data if isinstance(input_data, str) else input_data.read().decode('utf-8')
            df = pd.read_json(io.StringIO(json_string))

        elif input_format == 'excel':
            # Excel files must be read as binary. Use io.BytesIO for in-memory handling.
            if isinstance(input_data, io.BytesIO):
                df = pd.read_excel(input_data)
            else:
                # If a file object from request.files is passed, it behaves like an IO stream
                df = pd.read_excel(input_data)

        if df is None:
            return None, "Unsupported input format or data type."

        # Drop any entirely empty columns/rows if present after reading
        df.dropna(axis=1, how='all', inplace=True)
        df.dropna(axis=0, how='all', inplace=True)
        
        if df.empty:
             return None, "Data is empty after processing."


        # --- STEP 2: Convert DataFrame to Output Format ---

        if output_format == 'csv':
            # Convert DataFrame to CSV string
            output_content = df.to_csv(index=False)
            mime_type = 'text/csv'

        elif output_format == 'json':
            # Convert DataFrame to JSON string (records orientation is often easiest to handle)
            output_content = df.to_json(orient='records', indent=4)
            mime_type = 'application/json'

        elif output_format == 'excel':
            # Excel requires binary data. Use io.BytesIO to create an Excel file in memory.
            output_buffer = io.BytesIO()
            with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            output_buffer.seek(0)
            
            # Read the binary data back for base64 encoding
            output_content = base64.b64encode(output_buffer.read()).decode('utf-8')
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        else:
            return None, "Unsupported output format."

        # Return the content and its MIME type
        return output_content, mime_type

    except Exception as e:
        # Log the error for debugging and return a user-friendly message
        app.logger.error(f"Conversion error: {e}", exc_info=True)
        return None, f"Error during conversion: {str(e)}"

@app.route('/', methods=['GET'])
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def handle_convert():
    """Handles the conversion request from the frontend."""
    
    input_format = request.form.get('inputFormat')
    output_format = request.form.get('outputFormat')
    
    input_data = None
    data_source = request.form.get('dataSource')

    # Determine data source: File Upload or Pasted Text
    if data_source == 'file':
        uploaded_file = request.files.get('file')
        if not uploaded_file or uploaded_file.filename == '':
            return jsonify({'error': 'No file selected for upload.'}), 400
        
        # Read file content into memory stream (BytesIO for Excel, file object for others)
        if input_format == 'excel':
            input_data = io.BytesIO(uploaded_file.read())
        else:
            # Flask's FileStorage object acts like a file stream for text formats
            input_data = uploaded_file

    elif data_source == 'paste':
        pasted_text = request.form.get('pastedData')
        if not pasted_text:
            return jsonify({'error': 'No data pasted.'}), 400
        
        # For text inputs (CSV, JSON), use the string content
        input_data = pasted_text
        # Excel can't be pasted as text and converted easily, so we add a check
        if input_format == 'excel':
             return jsonify({'error': 'Excel conversion is only supported via file upload.'}), 400
    
    else:
        return jsonify({'error': 'Invalid data source specified.'}), 400

    # Perform the conversion
    converted_content, mime_type = convert_data(input_data, input_format, output_format)

    if converted_content is None:
        return jsonify({'error': mime_type}), 400

    # If the output is Excel (binary), the content is already base64 encoded.
    # Otherwise, it's a string (JSON/CSV).
    is_base64 = (output_format == 'excel')

    return jsonify({
        'success': True,
        'content': converted_content,
        'mimeType': mime_type,
        'isBase64': is_base64
    })

if __name__ == '__main__':
    # Run the app in debug mode for easy development
    print("Running Flask app on http://127.0.0.1:5000/")
    app.run(debug=True)
