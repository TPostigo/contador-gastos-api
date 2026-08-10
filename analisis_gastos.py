import pandas as pd
import matplotlib.pyplot as plt

# ---------- 1. Cargar el CSV ----------
# sep=';' porque exportamos con punto y coma
# parse_dates convierte la columna fecha de texto a tipo fecha real
df = pd.read_csv('gastos.csv', sep=';', parse_dates=['fecha'])

print('=== Primeras filas ===')
print(df.head())

print('\n=== Info general ===')
print(df.info())

# ---------- 2. Estadísticas básicas del importe ----------
print('\n=== Estadísticas de importe ===')
print(df['importe'].describe())

# ---------- 3. Gasto total y por categoría ----------
total = df['importe'].sum()
print(f'\nGasto total: {total:.2f} €')

# groupby: tu GROUP BY de SQL
por_categoria = df.groupby('categoria')['importe'].agg(['sum', 'mean', 'count'])
por_categoria = por_categoria.sort_values('sum', ascending=False)
print('\n=== Por categoría (total, media, nº gastos) ===')
print(por_categoria)

# ---------- 4. Evolución mensual ----------
# dt.to_period('M') agrupa las fechas por mes (2026-07, 2026-08...)
df['mes'] = df['fecha'].dt.to_period('M')
por_mes = df.groupby('mes')['importe'].sum()
print('\n=== Gasto por mes ===')
print(por_mes)

# ---------- 5. Día de la semana que más gastas ----------
df['dia_semana'] = df['fecha'].dt.day_name()
por_dia = df.groupby('dia_semana')['importe'].sum().sort_values(ascending=False)
print('\n=== Gasto por día de la semana ===')
print(por_dia)

# ---------- 6. Top 5 gastos más grandes ----------
print('\n=== Top 5 gastos ===')
top5 = df.nlargest(5, 'importe')[['descripcion', 'importe', 'categoria', 'fecha']]
print(top5)


# ---------- 7. Gráfica de barras: gasto por categoría ----------
fig, ax = plt.subplots(figsize=(8, 5))

datos_cat = df.groupby('categoria')['importe'].sum().sort_values(ascending=False)

ax.bar(datos_cat.index, datos_cat.values, color='#6366f1')
ax.set_title('Gasto total por categoría')
ax.set_ylabel('Importe (€)')

# Etiqueta con el valor encima de cada barra
for i, valor in enumerate(datos_cat.values):
    ax.text(i, valor, f'{valor:.2f} €', ha='center', va='bottom')

plt.tight_layout()
plt.savefig('gastos_por_categoria.png', dpi=150)
print('Guardada: gastos_por_categoria.png')

# ---------- 8. Gráfica de línea: evolución mensual ----------
fig, ax = plt.subplots(figsize=(8, 5))

datos_mes = df.groupby('mes')['importe'].sum()

# .astype(str) porque matplotlib no sabe pintar Periods directamente
ax.plot(datos_mes.index.astype(str), datos_mes.values,
        marker='o', linewidth=2, color='#8b5cf6')
ax.set_title('Evolución del gasto mensual')
ax.set_ylabel('Importe (€)')
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('evolucion_mensual.png', dpi=150)
print('Guardada: evolucion_mensual.png')

# ---------- 9. Gráfica de tarta: reparto porcentual ----------
fig, ax = plt.subplots(figsize=(6, 6))

ax.pie(datos_cat.values, labels=datos_cat.index,
       autopct='%1.1f%%', startangle=90,
       colors=['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'])
ax.set_title('Reparto del gasto')

plt.tight_layout()
plt.savefig('reparto_gastos.png', dpi=150)
print('Guardada: reparto_gastos.png')