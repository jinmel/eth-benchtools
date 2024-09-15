import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Function to read and combine CSV files
def read_csv_files(folder_path):
    """
    Reads all CSV files in the specified folder and concatenates them into a single DataFrame.
    """
    dataframes = []
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            filepath = os.path.join(folder_path, filename)
            df = pd.read_csv(filepath)
            dataframes.append(df)
    combined_df = pd.concat(dataframes, ignore_index=True)
    return combined_df

# Specify the folder containing your CSV files
folder_path = 'data-eth-erc20'  # Replace with your folder path

# Create a directory to save plots if it doesn't exist
plots_dir = 'plots'
if not os.path.exists(plots_dir):
    os.makedirs(plots_dir)

# Read and combine CSV files into a DataFrame
df = read_csv_files(folder_path)

# Data Preprocessing
# Convert time columns from milliseconds to datetime
df['start_time'] = pd.to_datetime(df['start_time'], unit='ms')
df['end_time'] = pd.to_datetime(df['end_time'], unit='ms')

# Calculate 'time_to_include' in milliseconds if not already accurate
df['time_to_include'] = (df['end_time'] - df['start_time']).dt.total_seconds() * 1000  # in milliseconds

# Sample 0.5% of the DataFrame for plotting if needed
sampled_df = df.sample(frac=0.005, random_state=42)

# Initialize plot counter and plots_info list
plot_counter = 1
plots_info = []

# 1. Histogram of Transaction Confirmation Times (Time to Include)
plt.figure(figsize=(10, 6))
plt.hist(df['time_to_include'], bins=20, edgecolor='k')
plot_title = 'Histogram of Transaction Confirmation Times'
plt.title(plot_title)
plt.xlabel('Time to Include (ms)')
plt.ylabel('Frequency')
# Save the plot
plot_filename = f'plot_{plot_counter}_histogram_confirmation_times.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 2. Time Series of Confirmation Times (Sampled Data)
plt.figure(figsize=(10, 6))
plt.scatter(sampled_df['start_time'], sampled_df['time_to_include'], marker='o')
plot_title = 'Time Series of Confirmation Times (Sampled 0.5%)'
plt.title(plot_title)
plt.xlabel('Start Time')
plt.ylabel('Time to Include (ms)')
plt.xticks(rotation=45)
plt.tight_layout()
# Save the plot
plot_filename = f'plot_{plot_counter}_time_series_confirmation_times.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 3. Box Plot of Confirmation Times by Transaction Type
plt.figure(figsize=(10, 6))
sns.boxplot(x='kind', y='time_to_include', data=df)
plot_title = 'Confirmation Times by Transaction Type'
plt.title(plot_title)
plt.xlabel('Transaction Type')
plt.ylabel('Time to Include (ms)')
plt.xticks(rotation=45)
# Save the plot
plot_filename = f'plot_{plot_counter}_boxplot_confirmation_times.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 4. Histogram of Gas Used
plt.figure(figsize=(10, 6))
plt.hist(df['gas_used'], bins=20, edgecolor='k')
plot_title = 'Histogram of Gas Used'
plt.title(plot_title)
plt.xlabel('Gas Used')
plt.ylabel('Frequency')
# Save the plot
plot_filename = f'plot_{plot_counter}_histogram_gas_used.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 5. Bar Chart of Average Gas Used per Transaction Type
avg_gas = df.groupby('kind')['gas_used'].mean().reset_index()
plt.figure(figsize=(10, 6))
sns.barplot(x='kind', y='gas_used', data=avg_gas)
plot_title = 'Average Gas Used per Transaction Type'
plt.title(plot_title)
plt.xlabel('Transaction Type')
plt.ylabel('Average Gas Used')
plt.xticks(rotation=45)
# Save the plot
plot_filename = f'plot_{plot_counter}_bar_chart_avg_gas_used.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 6. Scatter Plot of Gas Used vs. Confirmation Time
plt.figure(figsize=(10, 6))
plt.scatter(df['gas_used'], df['time_to_include'], alpha=0.7)
plot_title = 'Gas Used vs. Confirmation Time'
plt.title(plot_title)
plt.xlabel('Gas Used')
plt.ylabel('Time to Include (ms)')
# Save the plot
plot_filename = f'plot_{plot_counter}_scatter_gas_vs_confirmation_time.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 8. Pie Chart of Transaction Types
type_counts = df['kind'].value_counts()
plt.figure(figsize=(8, 8))
plt.pie(type_counts, labels=type_counts.index, autopct='%1.1f%%', startangle=140)
plot_title = 'Distribution of Transaction Types'
plt.title(plot_title)
plt.axis('equal')
# Save the plot
plot_filename = f'plot_{plot_counter}_pie_chart_transaction_types.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 10. Cumulative Gas Used Over Time
df.sort_values('end_time', inplace=True)
df['cumulative_gas'] = df['gas_used'].cumsum()
plt.figure(figsize=(10, 6))
plt.plot(df['end_time'], df['cumulative_gas'])
plot_title = 'Cumulative Gas Used Over Time'
plt.title(plot_title)
plt.xlabel('End Time')
plt.ylabel('Cumulative Gas Used')
plt.xticks(rotation=45)
plt.tight_layout()
# Save the plot
plot_filename = f'plot_{plot_counter}_cumulative_gas_over_time.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 11. Average Confirmation Time per Block
avg_time_per_block = df.groupby('block_number')['time_to_include'].mean().reset_index()
plt.figure(figsize=(10, 6))
plt.plot(avg_time_per_block['block_number'], avg_time_per_block['time_to_include'], marker='o')
plot_title = 'Average Confirmation Time per Block'
plt.title(plot_title)
plt.xlabel('Block Number')
plt.ylabel('Average Time to Include (ms)')
# Save the plot
plot_filename = f'plot_{plot_counter}_avg_confirmation_time_per_block.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 12. Distribution of Transactions per Block
transactions_per_block = df['block_number'].value_counts().reset_index()
transactions_per_block.columns = ['block_number', 'transaction_count']
plt.figure(figsize=(10, 6))
plt.bar(transactions_per_block['block_number'], transactions_per_block['transaction_count'])
plot_title = 'Transactions per Block'
plt.title(plot_title)
plt.xlabel('Block Number')
plt.ylabel('Number of Transactions')
# Save the plot
plot_filename = f'plot_{plot_counter}_transactions_per_block.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# 13. Line Chart of Gas Used Over Time
plt.figure(figsize=(10, 6))
plt.plot(df['end_time'], df['gas_used'], marker='o')
plot_title = 'Gas Used Over Time'
plt.title(plot_title)
plt.xlabel('End Time')
plt.ylabel('Gas Used')
plt.xticks(rotation=45)
plt.tight_layout()
# Save the plot
plot_filename = f'plot_{plot_counter}_gas_used_over_time.png'
plt.savefig(os.path.join(plots_dir, plot_filename))
plt.close()
# Add plot info to the list
plots_info.append((plot_filename, plot_title))
plot_counter += 1

# Generate the Markdown file
markdown_filename = 'plots.md'
with open(markdown_filename, 'w') as md_file:
    md_file.write('# Ethereum Transaction Plots\n\n')
    for filename, title in plots_info:
        md_file.write(f'## {title}\n\n')
        md_file.write(f'![{title}](./{plots_dir}/{filename})\n\n')

print(f"Plots have been saved to the '{plots_dir}' directory.")
print(f"Markdown file '{markdown_filename}' has been generated.")

