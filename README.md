# Football Predictor — LaLiga & Primeira Liga

Plataforma predictiva de fútbol europeo (LaLiga EA Sports + Primeira Liga
portuguesa), temporada 2026-2027, construida con Dixon-Coles (Poisson
bivariado con decaimiento temporal) y simulación Monte Carlo (10,000
simulaciones por partido) para proyectar resultados y la tabla final.

## App

```
pip install -r requirements.txt
streamlit run app.py
```

- Marcador proyectado vs. resultado real por jornada jugada.
- Próxima jornada: marcador proyectado, probabilidad 1X2 y los 3
  resultados exactos más probables.
- Precisión histórica del modelo, mapa de calor ofensivo y tabla
  proyectada (Top 4).

## Pipeline / Data Lake

Data Lake local en Parquet (Bronze → Silver → Gold), particionado por
liga/temporada bajo `data/`. Ver los notebooks en la raíz para cada etapa
(extracción, resolución de equipos, ratings Dixon-Coles, predicciones,
simulaciones de temporada).

Banderas de país en vez de escudos de club, por tema de copyright.
