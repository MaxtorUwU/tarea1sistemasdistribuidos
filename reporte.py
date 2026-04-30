import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

def generar_reporte_completo(file_path="resultados_detallados.csv"):
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"❌ No se encontró {file_path}")
        return

    sns.set_theme(style="whitegrid")
    
    # Lista de métricas que vamos a graficar
    metricas = ['hit_rate', 'throughput', 'p50', 'efficiency']
    
    for metrica in metricas:
        # catplot crea columnas (col="distribution") automáticamente
        g = sns.catplot(
            data=df, 
            kind="bar",
            x="size_MB", 
            y=metrica, 
            hue="policy", 
            col="distribution", # Esto divide Zipf y Uniform en dos cuadros
            height=5, 
            aspect=1.2, 
            palette="muted"
        )
        
        # Títulos y ajustes estéticos
        g.fig.subplots_adjust(top=0.85)
        g.fig.suptitle(f'Comparativa de {metrica.upper()}: Zipf vs Uniforme', fontsize=16)
        g.set_axis_labels("Tamaño de Memoria (MB)", metrica.upper())
        g.set_titles("Distribución: {col_name}")
        
        # Guardar gráfico individual
        nombre_archivo = f'grafico_comparativo_{metrica}.png'
        plt.savefig(nombre_archivo)
        print(f"✅ Guardado: {nombre_archivo}")
        plt.close()

    # GRÁFICO EXTRA: EVICTION RATE
    # También generamos el de evicciones separado para ver cómo se comporta la caché
    g_evic = sns.catplot(
        data=df, kind="bar",
        x="size_MB", y="eviction_rate", hue="policy", col="distribution",
        height=5, aspect=1.2, palette="dark"
    )
    g_evic.fig.subplots_adjust(top=0.85)
    g_evic.fig.suptitle('Tasa de Evicción (Evicciones/min): Zipf vs Uniforme', fontsize=16)
    g_evic.set_axis_labels("Tamaño de Memoria (MB)", "Evicciones / Minuto")
    g_evic.set_titles("Distribución: {col_name}")
    plt.savefig('grafico_comparativo_eviction_rate.png')
    print("✅ Guardado: grafico_comparativo_eviction_rate.png")
    plt.close()