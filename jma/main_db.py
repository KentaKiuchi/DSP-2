import requests
import sqlite3
import flet as ft
from datetime import datetime, timedelta

# API URL
AREA_LIST_URL = "http://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_URL_TEMPLATE = "https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"

# 天気コードと対応する天気の説明のマッピング
weather_code_mapping = {
    "100": "晴れ", "101": "晴れ 時々 曇り", "102": "晴れ 時々 雨", "104": "晴れ 時々 雪",
    "110": "晴れ 後 曇り", "112": "晴れ 後 雨", "115": "晴れ 後 雪", "200": "曇り",
    "201": "曇り 時々 晴れ", "202": "曇り 時々 雨", "204": "曇り 時々 雪", "210": "曇り 後 晴れ",
    "212": "曇り 後 雨", "215": "曇り 後 雪", "300": "雨", "301": "雨 時々 晴れ",
    "302": "雨 時々 曇り", "303": "雨 時々 雪", "308": "大雨", "311": "雨 後 晴れ",
    "313": "雨 後 曇り", "314": "雨 後 雪", "400": "雪", "401": "雪 時々 晴れ",
    "402": "雪 時々 曇り", "403": "雪 時々 雨", "406": "大雪", "411": "雪 後 晴れ",
    "413": "雪 後 曇り", "414": "雪 後 雨"
}

def reset_tables():
    conn = sqlite3.connect('weather_forecast_v3.db')
    cursor = conn.cursor()
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS region (
        region_id TEXT PRIMARY KEY,
        region_name TEXT
    );
    CREATE TABLE IF NOT EXISTS prefecture (
        prefecture_id TEXT PRIMARY KEY,
        prefecture_name TEXT,
        region_id TEXT,
        FOREIGN KEY(region_id) REFERENCES region(region_id)
    );
    CREATE TABLE IF NOT EXISTS area (
        area_id TEXT PRIMARY KEY,
        area_name TEXT,
        prefecture_id TEXT,
        FOREIGN KEY(prefecture_id) REFERENCES prefecture(prefecture_id)
    );
    CREATE TABLE IF NOT EXISTS weather (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_id TEXT,
        area_name TEXT,
        date TEXT,
        weather_code TEXT,
        weather_description TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(area_id, date, weather_code)
    );
    ''')
    conn.commit()
    conn.close()

def insert_area_data():
    response = requests.get(AREA_LIST_URL)
    area_data = response.json()
    regions = area_data["centers"]
    prefectures = area_data["offices"]
    areas = area_data["class10s"]
    
    conn = sqlite3.connect('weather_forecast_v3.db')
    cursor = conn.cursor()
    
    for region_id, region_info in regions.items():
        cursor.execute('INSERT OR IGNORE INTO region (region_id, region_name) VALUES (?, ?)', (region_id, region_info["name"]))
    
    for prefecture_id, prefecture_info in prefectures.items():
        cursor.execute('INSERT OR IGNORE INTO prefecture (prefecture_id, prefecture_name, region_id) VALUES (?, ?, ?)', (prefecture_id, prefecture_info["name"], prefecture_info["parent"]))
        
        for child_area_code in prefecture_info.get("children", []):
            area_name = areas[child_area_code]["name"]
            cursor.execute('INSERT OR IGNORE INTO area (area_id, area_name, prefecture_id) VALUES (?, ?, ?)', (child_area_code, area_name, prefecture_id))
    
    conn.commit()
    conn.close()

def get_forecast(area_code):
    response = requests.get(FORECAST_URL_TEMPLATE.format(area_code=area_code))
    response.raise_for_status()
    return response.json()

def insert_weather_data():
    conn = sqlite3.connect('weather_forecast_v3.db')
    cursor = conn.cursor()
    cursor.execute('SELECT prefecture_id, prefecture_name FROM prefecture')
    prefecture_ids_and_names = cursor.fetchall()
    
    for prefecture_id, prefecture_name in prefecture_ids_and_names:
        try:
            print(f"Fetching data for prefecture {prefecture_id} ({prefecture_name})...")
            forecast_data = get_forecast(prefecture_id)
            if forecast_data:
                timeSeries = forecast_data[0].get("timeSeries", [])
                if timeSeries:
                    time_defines = timeSeries[0].get("timeDefines", [])
                    areas = timeSeries[0].get("areas", [])
                    for area in areas:
                        area_code = area["area"]["code"]
                        area_name = area["area"]["name"]
                        for i, date in enumerate(time_defines[:3]):
                            if i < len(area["weatherCodes"]):
                                weather_code = area["weatherCodes"][i]
                                weather_description = weather_code_mapping.get(weather_code, "不明な天気")
                                cursor.execute('''
                                INSERT OR REPLACE INTO weather (area_id, area_name, date, weather_code, weather_description, updated_at)
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                                ''', (area_code, area_name, date, weather_code, weather_description))
        except requests.exceptions.HTTPError as e:
            print(f"HTTPError for prefecture {prefecture_id}: {e}")
        except requests.RequestException as e:
            print(f"RequestException for prefecture {prefecture_id}: {e}")
    
    conn.commit()
    conn.close()

def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.scroll = "adaptive"
    page.window_width = 800
    page.window_height = 600

    conn = sqlite3.connect('weather_forecast_v3.db')
    cursor = conn.cursor()
    cursor.execute('SELECT region_id, region_name FROM region')
    regions = cursor.fetchall()

    selected_region = ft.Text("")
    selected_office = ft.Text("")
    forecast_display = ft.Column(spacing=20)
    office_dropdown = ft.Dropdown(
        width=200,
        label="都道府県を選択"
    )
    date_dropdown = ft.Dropdown(
        width=200,
        label="日付を選択",
        options=[],
        on_change=lambda e: update_forecast(e.data)
    )

    def select_region(e):
        region_id = e.data
        selected_region.value = f"選択中の地方: {dict(regions)[region_id]}"
        selected_office.value = ""
        office_dropdown.options = []
        cursor.execute('SELECT prefecture_id, prefecture_name FROM prefecture WHERE region_id = ?', (region_id,))
        offices = cursor.fetchall()
        for office in offices:
            office_dropdown.options.append(ft.dropdown.Option(office[0], office[1]))
        office_dropdown.value = None
        forecast_display.controls.clear()
        date_dropdown.options = []
        page.update()

    def select_office(e):
        forecast_display.controls.clear()
        office_code = e.data
        cursor.execute('SELECT area_id, area_name FROM area WHERE prefecture_id = ?', (office_code,))
        areas = cursor.fetchall()

        if areas:
            cursor.execute('SELECT prefecture_name FROM prefecture WHERE prefecture_id = ?', (office_code,))
            prefecture = cursor.fetchone()
            selected_office.value = f"選択中の地域: {prefecture[0]}"

            cursor.execute('''
                SELECT DISTINCT date FROM weather 
                WHERE area_id IN (SELECT area_id FROM area WHERE prefecture_id = ?) 
                ORDER BY date
            ''', (office_code,))
            available_dates = cursor.fetchall()

            date_dropdown.options = [
                ft.dropdown.Option(date[0], datetime.strptime(date[0], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y/%m/%d"))
                for date in available_dates
            ]

        page.update()

    def update_forecast(selected_date):
        forecast_display.controls.clear()
        cursor = sqlite3.connect('weather_forecast_v3.db').cursor()
        office_code = office_dropdown.value
        cursor.execute('SELECT area_id, area_name FROM area WHERE prefecture_id = ?', (office_code,))
        areas = cursor.fetchall()

        for area_id, area_name in areas:
            cursor.execute('''
                SELECT date, weather_code, weather_description, updated_at
                FROM weather
                WHERE area_id = ? AND date = ?
                ORDER BY updated_at DESC
            ''', (area_id, selected_date))
            weather_data = cursor.fetchall()

            forecast_display.controls.extend([
                ft.Text(f"{area_name}の天気予報", size=20, weight="bold"),
                ft.Container(
                    content=ft.Row(
                        spacing=10,
                        scroll=ft.ScrollMode.ALWAYS,
                        controls=[
                            ft.Card(
                                content=ft.Container(
                                    width=160,
                                    height=250,
                                    content=ft.Column(
                                        [
                                            ft.Text(f"{date[:10]}", size=16, text_align=ft.TextAlign.CENTER),
                                            ft.Image(
                                                src=f'https://www.jma.go.jp/bosai/forecast/img/{weather_code}.png',
                                                width=60,
                                                height=60
                                            ),
                                            ft.Text(weather_description, size=14, text_align=ft.TextAlign.CENTER),
                                            ft.Text(f"更新: {updated_at[:19]}", size=10, text_align=ft.TextAlign.CENTER)
                                        ],
                                        spacing=10,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    padding=ft.padding.all(8),
                                    bgcolor=ft.colors.BLUE_GREY_50,
                                    border_radius=ft.border_radius.all(12),
                                ),
                                elevation=5,
                            )
                            for date, weather_code, weather_description, updated_at in weather_data
                        ],
                        wrap=False
                    ),
                    height=300,
                    width=page.window_width - 260,
                )
            ] or [ft.Text("天気情報がありません")])
        page.update()

    region_dropdown = ft.Dropdown(
        width=200,
        label="地方を選択",
        options=[ft.dropdown.Option(code, name) for code, name in regions],
        on_change=select_region
    )

    office_dropdown.on_change = select_office

    selection_container = ft.Container(
        alignment=ft.alignment.top_left,
        width=240,
        padding=ft.padding.all(10),
        content=ft.Column(
            [
                region_dropdown,
                selected_region,
                office_dropdown,
                selected_office,
                date_dropdown,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.CrossAxisAlignment.START,
        ),
    )

    page.add(
        ft.Row(
            alignment=ft.MainAxisAlignment.START,
            controls=[
                selection_container,
                ft.Container(
                    expand=True,
                    padding=ft.padding.all(10),
                    content=forecast_display,
                ),
            ],
            expand=True,
        )
    )

def initialize_app():
    reset_tables()
    insert_area_data()
    insert_weather_data()

if __name__ == "__main__":
    initialize_app()
    ft.app(target=main)