from base.types import tool


@tool
def get_weather(city: str) -> str:
    """获取一个城市的天气"""
    return f"{city}的天气是晴天"


@tool(name="get_temperature", description="获取指定城市的温度")
def get_temperature(city: str, unit: str = "celsius") -> str:
    return f"{city}的温度: 25°{unit}"
