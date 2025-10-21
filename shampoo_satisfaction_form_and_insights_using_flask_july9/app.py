from flask import Flask, render_template, request, redirect, flash
import mysql.connector
from mysql.connector import Error
import os
import pandas as pd
import plotly.express as px
import matplotlib
# matplotlib.use('Agg')
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import csv

app = Flask(__name__)
#app.secret_key = 'your_secret_key'

# --- MySQL Configuration ---
DB_HOST = os.environ.get('MYSQL_HOST')
DB_USER = os.environ.get('MYSQL_USER')
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD')
DB_NAME = os.environ.get('MYSQL_DB')

CSV_FILE = 'latest_survey_dashboard.csv'  # optional local CSV

# --- DB Setup ---
def create_db():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                age_group VARCHAR(50),
                gender VARCHAR(50),
                city VARCHAR(100),
                state VARCHAR(100),
                mobile VARCHAR(20),
                email VARCHAR(255),
                used VARCHAR(10),
                shampoo VARCHAR(255),
                usage_duration VARCHAR(50),
                satisfaction VARCHAR(10),
                reason TEXT,
                recommend VARCHAR(10)
            )
        ''')
        conn.commit()
        c.close()
        conn.close()
    except Error as e:
        print("Error creating MySQL table:", e)

create_db()

# --- Helper Functions ---
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def is_email_already_used(email):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM responses WHERE LOWER(email)=%s", (email.lower(),))
        result = c.fetchone()
        c.close()
        conn.close()
        return result is not None
    except Error as e:
        print("Error checking email:", e)
        return False

def export_db_to_csv():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM responses")
        rows = c.fetchall()
        headers = [i[0] for i in c.description]
        c.close()
        conn.close()
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    except Error as e:
        print("Error exporting CSV:", e)

def univariate(data, var):
    df = data[var].value_counts().reset_index(name="Count").rename(columns={"index": var})
    total = df['Count'].sum()
    df['Percentage'] = round(df['Count'] / total * 100, 1)
    df['Label'] = df['Percentage'].astype(str) + '%'
    return df

def bivariate_city_state(data):
    data['state'] = data['state'].str.strip().str.title()
    data['city'] = data['city'].str.strip().str.title()
    df = data.groupby(['state', 'city']).size().reset_index(name="Count")
    total_by_state = df.groupby('state')['Count'].transform('sum')
    df['Percentage'] = round(df['Count'] / total_by_state * 100, 1)
    df['Label'] = df['Percentage'].astype(str) + '%'
    return df

def get_summary_cards(df):
    total_users = len(df)
    shampoo_users = df[df['used'].str.lower() == 'yes']
    percent_shampoo_users = round(len(shampoo_users) / total_users * 100) if total_users else 0
    top_rated = shampoo_users[shampoo_users['satisfaction'].str.startswith(('4', '5'))]
    percent_top_rated = round(len(top_rated) / len(shampoo_users) * 100) if len(shampoo_users) else 0
    recommend_yes = shampoo_users[shampoo_users['recommend'].str.lower() == 'yes']
    percent_recommend = round(len(recommend_yes) / len(shampoo_users) * 100) if len(shampoo_users) else 0
    return total_users, f"{percent_shampoo_users}%", f"{percent_top_rated}%", f"{percent_recommend}%"

# --- Routes ---
@app.route('/')
def main():
    return render_template('main.html')

@app.route('/form', methods=['GET', 'POST'])
def survey_form():
    if request.method == 'POST':
        email = request.form.get('email')
        if is_email_already_used(email):
            flash("You've already responded with this email!")
            return redirect('/form')

        fields = ['name', 'age_group', 'gender', 'city', 'state', 'mobile', 'email', 'used']
        data = {field: request.form.get(field) for field in fields}
        data.update({'shampoo': '', 'usage_duration': '', 'satisfaction': '', 'reason': '', 'recommend': ''})

        if data['used'] == 'yes':
            data['shampoo'] = request.form.get('shampoo')
            if data['shampoo'] == 'others':
                data['shampoo'] = request.form.get('other_shampoo')
            for f in ['usage_duration', 'satisfaction', 'reason', 'recommend']:
                data[f] = request.form.get(f)

        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute('''
                INSERT INTO responses (name, age_group, gender, city, state, mobile, email,
                used, shampoo, usage_duration, satisfaction, reason, recommend)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', tuple(data.values()))
            conn.commit()
            c.close()
            conn.close()
        except Error as e:
            print("Error inserting survey response:", e)

        export_db_to_csv()
        return redirect('/thankyou')
    return render_template('form.html')

@app.route('/thankyou')
def thankyou():
    return render_template('thankyou.html')

@app.route('/dashboard')
def dashboard():
    df = pd.read_csv(CSV_FILE)
    df.dropna(subset=['used'], inplace=True)
    shampoo_df = df[df['used'].str.lower() == 'yes']

    total_users, percent_shampoo_users, percent_top_rated, percent_recommend = get_summary_cards(df)

    charts = {}
    pie_vars = ['used', 'gender']
    for var in ['used', 'age_group', 'gender', 'shampoo', 'usage_duration', 'satisfaction', 'recommend']:
        data = df if var in ['used', 'age_group', 'gender'] else shampoo_df
        chart_df = univariate(data, var)

        fig = None
        if var in pie_vars:
            fig = px.pie(chart_df, names=var, values='Count', hole=0.3)
            fig.update_traces(textinfo='percent+label', textfont_size=12)
            fig.update_layout(showlegend=False)
        else:
            fig = px.bar(chart_df, x=var, y='Percentage', color=var, text_auto=True)
            fig.update_traces(
                textfont=dict(size=14, family='Arial Black', color='black'),
                marker_line_width=1.5,
                marker_line_color='black'
            )
            fig.update_layout(
                uniformtext_minsize=12,
                uniformtext_mode='show',
                xaxis_tickangle=-45,
                showlegend=False,
                height=500,
                margin=dict(t=50, b=80, l=40, r=40),
                yaxis=dict(range=[0, max(30, chart_df['Percentage'].max() + 20)])
            )
        charts[var] = fig.to_html(full_html=False)

    # --- City-wise Chart ---
    bivar_df = bivariate_city_state(df)
    fig = px.bar(
        bivar_df, x='city', y='Percentage',
        color='state', barmode='group',
        text_auto=True
    )
    fig.update_traces(
        textfont=dict(size=10, family='Arial Black', color='black'),
        marker_line_width=1.5,
        marker_line_color='black'
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        showlegend=False,
        height=500,
        margin=dict(t=50, b=80, l=40, r=40),
        yaxis=dict(range=[0, max(30, bivar_df['Percentage'].max() + 20)])
    )
    charts['location'] = fig.to_html(full_html=False)

    # --- WordCloud (optional) ---
    '''os.makedirs('static/charts', exist_ok=True)
    text = ' '.join(df['reason'].dropna().astype(str))
    wordcloud = WordCloud(width=600, height=400, background_color='white', colormap='viridis').generate(text)
    plt.figure(figsize=(6, 4))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.tight_layout(pad=0)
    plt.savefig('static/charts/reason_wc.png')
    plt.close()'''

    return render_template(
        'dashboard.html',
        total=total_users,
        percent_shampoo_users=percent_shampoo_users,
        percent_top_satisfaction=percent_top_rated,
        percent_recommend=percent_recommend,
        plot_used=charts['used'],
        plot_age_group=charts['age_group'],
        plot_gender=charts['gender'],
        plot_location=charts['location'],
        plot_shampoo=charts['shampoo'],
        plot_duration=charts['usage_duration'],
        plot_satisfaction=charts['satisfaction'],
        plot_recommend=charts['recommend']
    )

if __name__ == '__main__':
    app.run(debug=True)
