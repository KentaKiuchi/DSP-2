import requests
import flet as ft

# 地域リストのエンドポイント
AREA_LIST_URL = "http://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_URL_TEMPLATE = "https://www.jma.go.jp/bosai/forecast/data/forecast/{region_code}.json"

# 天気コードと対応する天気の説明のマッピング
weather_code_mapping = {
    "100": "晴れ",
    "101": "晴れ 時々 曇り",
    "102": "晴れ 時々 雨",
    "104": "晴れ 時々 雪",
    "110": "晴れ 後 曇り",
    "112": "晴れ 後 雨",
    "115": "晴れ 後 雪",
    "200": "曇り",
    "201": "曇り 時々 晴れ",
    "202": "曇り 時々 雨",
    "204": "曇り 時々 雪",
    "210": "曇り 後 晴れ",
    "212": "曇り 後 雨",
    "215": "曇り 後 雪",
    "300": "雨",
    "301": "雨 時々 晴れ",
    "302": "雨 時々 曇り",
    "303": "雨 時々 雪",
    "308": "大雨",
    "311": "雨 後 晴れ",
    "313": "雨 後 曇り",
    "314": "雨 後 雪",
    "400": "雪",
    "401": "雪 時々 晴れ",
    "402": "雪 時々 曇り",
    "403": "雪 時々 雨",
    "406": "大雪",
    "411": "雪 後 晴れ",
    "413": "雪 後 曇り",
    "414": "雪 後 雨"
}

# 地域リストを取得
def get_area_list():
    response = requests.get(AREA_LIST_URL)
    response.raise_for_status()
    return response.json()

# 天気予報を取得
def get_forecast(region_code):
    response = requests.get(FORECAST_URL_TEMPLATE.format(region_code=region_code))
    response.raise_for_status()
    return response.json()

# 地方ごとのデータ構造を作成
def create_region_hierarchy(area_data):
    hierarchy = {}
    centers = area_data["centers"]
    offices = area_data["offices"]

    for center_code, center in centers.items():
        hierarchy[center_code] = {
            "name": center["name"],
            "offices": []
        }
        for child_code in center["children"]:
            office = offices.get(child_code)
            if office:
                hierarchy[center_code]["offices"].append({
                    "name": office["name"],
                    "code": child_code
                })

    return hierarchy

# Fletアプリ
def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.scroll = "adaptive"
    
    # ウィンドウサイズの設定
    page.window_width = 1100  # 幅を指定 (必要に応じて調整)
    page.window_height = 780  # 高さを指定 (必要に応じて調整)

    try:
        # 地域リストを取得
        area_data = get_area_list()
    except Exception as e:
        page.add(ft.Text(f"Error: {e}", color="red"))
        page.update()
        return

    region_hierarchy = create_region_hierarchy(area_data)

    # UIコンポーネント
    selected_region = ft.Text("")
    selected_office = ft.Text("")
    forecast_display = ft.Column(spacing=20)
    
    office_dropdown = ft.Dropdown()

    # 地方を選択する関数
    def select_region(e):
        region_code = e.data
        selected_region.value = f"選択中の地方: {region_hierarchy[region_code]['name']}"
        selected_office.value = ""
        office_dropdown.options = []

        for office in region_hierarchy[region_code]["offices"]:
            office_dropdown.options.append(ft.dropdown.Option(office["code"], office["name"]))

        office_dropdown.value = None
        forecast_display.controls.clear()
        page.update()

    # 都道府県を選択する関数
    def select_office(e):
        forecast_display.controls.clear()

        office_code = e.data
        selected_office.value = f"選択中の地域: {next((office['name'] for center in region_hierarchy.values() for office in center['offices'] if office['code'] == office_code), '')}"

        try:
            forecast_data = get_forecast(office_code)
        except requests.exceptions.HTTPError as http_err:
            forecast_display.controls.clear()
            forecast_display.controls.append(ft.Text(f"Error: {http_err}", color="red"))
            page.update()
            return
        except Exception as ex:
            forecast_display.controls.clear()
            forecast_display.controls.append(ft.Text(f"Error: {ex}", color="red"))
            page.update()
            return

        # 天気情報を表示
        if not forecast_data:
            forecast_display.controls.append(ft.Text("天気情報がありません"))
            page.update()
            return

        for forecast in forecast_data:
            time_series = forecast.get("timeSeries", [])
            for ts in time_series:
                times = ts.get("timeDefines", [])
                areas = ts.get("areas", [])

                for area in areas:
                    if "weathers" in area:
                        area_name = area["area"]["name"]
                        forecasts = []

                        for i in range(len(times)):
                            time = times[i][:10]
                            weather_code = area.get("weatherCodes", [])[i] if i < len(area.get("weatherCodes", [])) else None
                            weather = weather_code_mapping.get(weather_code, "不明な天気")

                            forecasts.append({
                                "time": time,
                                "weather": weather,
                                "weather_code": weather_code or ""
                            })

                        if forecasts:
                            forecast_display.controls.append(ft.Text(f"{area_name}", size=20, weight="bold"))
                            row = ft.Row(spacing=10, controls=[
                                ft.Container(
                                    width=160, height=200,
                                    content=ft.Column(
                                        [
                                            ft.Text(f'{forecast["time"]}', size=16, text_align=ft.TextAlign.CENTER),
                                            ft.Image(src=f'https://www.jma.go.jp/bosai/forecast/img/{forecast["weather_code"]}.png') if forecast["weather_code"] else ft.Container(),
                                            ft.Text(f'{forecast["weather"]}', size=14, text_align=ft.TextAlign.CENTER),
                                        ],
                                        spacing=10,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    ),
                                    padding=ft.padding.all(8),
                                    bgcolor=ft.colors.BLUE_GREY_50,
                                    border_radius=ft.border_radius.all(12),
                                ) for forecast in forecasts
                            ])
                            forecast_display.controls.append(row)

        page.update()

    # 地方リストのドロップダウン
    region_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(code, center["name"]) for code, center in region_hierarchy.items()],
        on_change=select_region
    )

    # 都道府県のドロップダウン
    office_dropdown.on_change = select_office

    # 左側の選択メニューのコンテナ
    selection_container = ft.Container(
        alignment=ft.alignment.top_left,  # 左上に固定
        width=240,  # 固定幅
        padding=ft.padding.all(10),
        content=ft.Column(
            [
                ft.Text("地方を選択", size=20, weight="bold"),
                region_dropdown,
                selected_region,
                ft.Text("都道府県を選択", size=20, weight="bold"),
                office_dropdown,
                selected_office,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.CrossAxisAlignment.START,  # 左揃え
        ),
    )

    # レイアウト
    page.add(
        ft.Row(
            alignment=ft.MainAxisAlignment.START,  # 左上に揃える
            controls=[
                selection_container,
                ft.VerticalDivider(width=1),
                ft.Container(
                    expand=True,
                    padding=ft.padding.all(10),
                    content=forecast_display
                ),
            ],
            expand=True,
        )
    )

ft.app(target=main)