import requests
import flet as ft

# 地域リストのエンドポイント
AREA_LIST_URL = "http://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_URL_TEMPLATE = "https://www.jma.go.jp/bosai/forecast/data/forecast/{region_code}.json"

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
    office_display = ft.ListView()
    forecast_display = ft.Column()

    # 地方を選択する関数
    def select_region(e):
        region_code = e.control.data["code"]
        region_name = e.control.data["name"]
        selected_region.value = f"選択中の地方: {region_name}"
        selected_office.value = ""
        office_display.controls.clear()

        for office in region_hierarchy[region_code]["offices"]:
            office_display.controls.append(
                ft.ListTile(
                    title=ft.Text(office["name"]),
                    data=office,
                    on_click=select_office,
                )
            )

        forecast_display.controls.clear()
        page.update()

    # 都道府県を選択する関数
    def select_office(e):
        office = e.control.data
        selected_office.value = f"選択中の地域: {office['name']}"
        try:
            forecast_data = get_forecast(office["code"])
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
        forecast_display.controls.clear()

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
                    area_name = area["area"]["name"]
                    forecasts = []
                    for i in range(len(times)):
                        time = times[i][:16]
                        weather = area.get("weathers", [])[i] if i < len(area.get("weathers", [])) else "情報なし"
                        wind = area.get("winds", [])[i] if i < len(area.get("winds", [])) else "情報なし"
                        wave = area.get("waves", [])[i] if i < len(area.get("waves", [])) else "情報なし"

                        if weather != "情報なし" or wind != "情報なし" or wave != "情報なし":
                            forecasts.append({
                                "time": time,
                                "weather": weather,
                                "wind": wind,
                                "wave": wave
                            })
                    
                    if forecasts:
                        forecast_display.controls.append(ft.Text(f"{area_name}", weight="bold"))
                        for forecast in forecasts:
                            forecast_display.controls.append(ft.Text(f"{forecast['time']}の天気: {forecast['weather']}"))
                            forecast_display.controls.append(ft.Text(f"風: {forecast['wind']}"))
                            forecast_display.controls.append(ft.Text(f"波: {forecast['wave']}"))
                            forecast_display.controls.append(ft.Divider())

        page.update()

    # 地方リストをリスト表示
    region_list_tiles = [
        ft.ListTile(
            title=ft.Text(center["name"]),
            data={"code": center_code, "name": center["name"]},
            on_click=select_region,
        )
        for center_code, center in region_hierarchy.items()
    ]

    # レイアウト
    page.add(
        ft.Row(
            controls=[
                ft.Container(
                    width=300,  # 固定幅
                    padding=ft.padding.all(10),
                    content=ft.Column(
                        [
                            ft.Text("地方を選択してください", size=20, weight="bold"),
                            ft.ListView(controls=region_list_tiles, expand=True, height=300),
                            ft.Container(content=selected_region, padding=10),
                            office_display,
                            ft.Container(content=selected_office, padding=10),
                        ],
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ),
                ft.VerticalDivider(width=1),
                ft.Container(
                    expand=True,
                    padding=ft.padding.all(10),
                    content=ft.Column(
                        expand=True,
                        controls=[forecast_display],
                    ),
                ),
            ],
            expand=True,
        )
    )

ft.app(target=main)