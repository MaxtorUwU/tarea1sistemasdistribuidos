import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generar_reporte_grafico(file_path="resultados_fase4.csv"):
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"❌ No se encontró {file_path}. Ejecuta primero el orquestador de experimentos.")
        return

    # Configuración de estilo
    sns.set_theme(style="whitegrid")
    plt.rcParams['figure.figsize'] = (10, 6)

    # --- GRÁFICO 1: HIT RATE VS TAMAÑO DE CACHÉ ---
    plt.figure()
    size_df = df[df['experiment'] == 'Size'].sort_values(by='value')
    sns.lineplot(data=size_df, x='value', y='hit_rate', marker='o', color='royalblue', linewidth=2.5)
    plt.title('Impacto del Tamaño de Memoria en el Hit Rate', fontsize=14)
    plt.xlabel('Tamaño de Memoria (MB)', fontsize=12)
    plt.ylabel('Hit Rate (0.0 - 1.0)', fontsize=12)
    plt.ylim(0, 1.1)
    plt.savefig('grafico_tamano_cache.png')
    print("✅ Guardado: grafico_tamano_cache.png")

    # --- GRÁFICO 2: HIT RATE VS POLÍTICA DE EVICCIÓN ---
    plt.figure()
    policy_df = df[df['experiment'] == 'Policy']
    sns.barplot(data=policy_df, x='value', y='hit_rate', palette='viridis')
    plt.title('Comparación de Políticas de Evicción (Zipf Traffic)', fontsize=14)
    plt.xlabel('Política de Redis', fontsize=12)
    plt.ylabel('Hit Rate (0.0 - 1.0)', fontsize=12)
    plt.ylim(0, 1.1)
    plt.savefig('grafico_politicas.png')
    print("✅ Guardado: grafico_politicas.png")

    # --- GRÁFICO 3: LATENCIA P50/P95 (Opcional si usas metrics_log.csv) ---
    # Este usa el archivo general de métricas para comparar Uniforme vs Zipf
    try:
        metrics_df = pd.read_csv("metrics_log.csv")
        # Aquí podrías segmentar las primeras 200 filas como Uniforme y el resto Zipf
        # según cómo ejecutaste el generador de tráfico.
    except:
        pass

if __name__ == "__main__":
    generar_reporte_grafico()