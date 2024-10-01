import requests


NEWS_CODE="e3e3d595845b4e878dd7f28480dc3823" # Asegúrate de reemplazar esto con tu clave de News API

def get_top_business_headlines():
    url = f"https://newsapi.org/v2/top-headlines?country=us&category=general&apiKey={NEWS_CODE}"
    
    try:
        response = requests.get(url)
        news_data = response.json()

        # Verificar si la solicitud fue exitosa
        if news_data.get('status') == 'ok':
            # Seleccionar los 3 primeros artículos de las noticias
            articles = news_data.get('articles', [])[:5]
            return articles
        else:
            print("Error al obtener las noticias:", news_data.get('message'))
            return []

    except Exception as e:
        print(f"Error al hacer la solicitud a la News API: {e}")
        return []


