from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import os

app = Flask(__name__)

# Load and prepare real data
df = pd.read_csv('NHANES_17_18_modified_data.csv')

X = df[['height']]
y = df['weight']

# Train the model
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = LinearRegression()
model.fit(X_train, y_train)

# Model performance (prints in console)
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
print(f"✅ MAE: {mae:.2f} kg | Model trained on real data")

@app.route('/', methods=['GET', 'POST'])
def index():
    prediction = None
    error = None
    height = ""

    if request.method == 'POST':
        if 'predict' in request.form:
            height = request.form.get('height')
            try:
                h = float(height)
                prediction = model.predict([[h]])[0]
            except:
                error = "❗ Please enter a valid number."
        elif 'reset' in request.form:
            return redirect(url_for('index'))

    return render_template('index.html', prediction=prediction, error=error, height=height)

#if __name__ == '__main__':
    #app.run(debug=True)

import os

if __name__ == '__main__':
    # Use 0.0.0.0 to listen on all public IPs
    # Use the PORT environment variable provided by Railway (or default to 5000)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
