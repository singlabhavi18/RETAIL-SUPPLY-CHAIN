import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import sys
import os

# Page configuration
st.set_page_config(
    page_title="Retail Supply Chain Dashboard",
    page_icon="📊",
    layout="wide"
)

# Add backend to Python path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Sidebar configuration
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select Section:",
    [
        "📊 Overview",
        "📈 Forecasting",
        "🛡️ Safety Stock",
        "🚨 Stockout Risk",
        "🔄 Restock Management",
        "📅 Mid-Month Prediction",
        "📤 Upload Sales",
        "🤖 AI Chatbot"
    ]
)

st.sidebar.markdown("---")

# API Configuration in sidebar
st.sidebar.subheader("Configuration")
API_URL = st.sidebar.text_input(
    "API URL",
    value="http://localhost:8000",
    help="Base URL of the FastAPI backend"
)

forecast_days = st.sidebar.slider(
    "Forecast Days",
    min_value=1,
    max_value=30,
    value=7,
    help="Number of days to forecast demand"
)

# Fetch data from API
@st.cache_data(ttl=60)
def fetch_data(api_url, forecast_days):
    """Fetch data from backend API"""
    try:
        inventory_response = requests.get(f"{api_url}/inventory")
        inventory_data = inventory_response.json() if inventory_response.status_code == 200 else []
        
        safety_stock_response = requests.get(f"{api_url}/safety-stock")
        safety_stock_data = safety_stock_response.json() if safety_stock_response.status_code == 200 else []
        
        restock_response = requests.get(f"{api_url}/restock-recommendations?forecast_days={forecast_days}")
        restock_data = restock_response.json() if restock_response.status_code == 200 else []
        
        stockout_response = requests.get(f"{api_url}/stockout-risk?n_days={forecast_days}")
        stockout_data = stockout_response.json() if stockout_response.status_code == 200 else []
        
        forecast_response = requests.get(f"{api_url}/forecast-next-month")
        forecast_data = forecast_response.json() if forecast_response.status_code == 200 else []
        
        mid_month_response = requests.get(f"{api_url}/mid-month-stockout-prediction")
        mid_month_data = mid_month_response.json() if mid_month_response.status_code == 200 else []
        
        return {
            "inventory": inventory_data,
            "safety_stock": safety_stock_data,
            "restock": restock_data,
            "stockout": stockout_data,
            "forecast": forecast_data,
            "mid_month": mid_month_data
        }
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return {
            "inventory": [],
            "safety_stock": [],
            "restock": [],
            "stockout": [],
            "forecast": [],
            "mid_month": []
        }

# Fetch data once
data = fetch_data(API_URL, forecast_days)

# ==================== OVERVIEW SECTION ====================
if page == "📊 Overview":
    st.title("📊 Overview Dashboard")
    st.markdown("---")
    
    # Metrics Row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_products = len(data["inventory"])
        st.metric(label="Total Products", value=total_products)
    
    with col2:
        products_at_risk = len([p for p in data["restock"] if p["recommended_order_qty"] > 0])
        st.metric(label="Products at Risk", value=products_at_risk, delta=f"{products_at_risk} need restock")
    
    with col3:
        total_restock = sum(p["recommended_order_qty"] for p in data["restock"])
        st.metric(label="Total Recommended Restock", value=total_restock, delta="units")
    
    st.markdown("---")
    
    # Forecasted Demand Chart
    st.subheader("📈 Forecasted Demand for Next Month")
    if data["forecast"]:
        forecast_df = pd.DataFrame(data["forecast"])
        fig = px.bar(
            forecast_df,
            x="product_name",
            y="forecast_units",
            title="Forecasted Demand by Product",
            color="forecast_units",
            color_continuous_scale="Viridis"
        )
        fig.update_layout(xaxis_title="Product", yaxis_title="Forecasted Units", height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No forecast data available")
    
    st.markdown("---")
    
    # Current Stock vs Predicted Demand
    st.subheader("📊 Current Stock vs Predicted Demand")
    if data["restock"]:
        restock_df = pd.DataFrame(data["restock"])
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Current Stock', x=restock_df['product_name'], y=restock_df['current_stock'], marker_color='blue'))
        fig.add_trace(go.Bar(name='Predicted Demand', x=restock_df['product_name'], y=restock_df.get(f'forecasted_demand_next_{forecast_days}days', [0]*len(restock_df)), marker_color='orange'))
        fig.update_layout(title='Current Stock vs Predicted Demand', xaxis_title='Product', yaxis_title='Units', barmode='group', height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No restock data available")

# ==================== FORECASTING SECTION ====================
elif page == "📈 Forecasting":
    st.title("📈 Demand Forecasting")
    st.markdown("---")
    
    st.subheader("Next Month Forecast")
    if data["forecast"]:
        forecast_df = pd.DataFrame(data["forecast"])
        fig = px.bar(forecast_df, x="product_name", y="forecast_units", color="forecast_units", color_continuous_scale="Plasma")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Forecast Data Table")
        st.dataframe(forecast_df, hide_index=True, use_container_width=True)
    else:
        st.info("No forecast data available")

# ==================== SAFETY STOCK SECTION ====================
elif page == "🛡️ Safety Stock":
    st.title("🛡️ Safety Stock & Reorder Points")
    st.markdown("---")
    
    if data["safety_stock"]:
        safety_stock_df = pd.DataFrame(data["safety_stock"])
        inventory_df = pd.DataFrame(data["inventory"])
        merged_df = safety_stock_df.merge(inventory_df[['product_name', 'current_stock']], on='product_name', how='left')
        merged_df['stock_status'] = merged_df.apply(lambda row: '⚠️ Below Reorder Point' if row['current_stock'] < row['reorder_point'] else '✅ OK', axis=1)
        
        # Status summary
        at_risk_count = len(merged_df[merged_df['stock_status'].str.contains('⚠️')])
        st.metric("Products Below Reorder Point", at_risk_count)
        
        st.markdown("---")
        st.subheader("Safety Stock Details")
        st.dataframe(
            merged_df,
            column_config={
                "product_name": st.column_config.TextColumn("Product Name"),
                "current_stock": st.column_config.NumberColumn("Current Stock", format="%d"),
                "reorder_point": st.column_config.NumberColumn("Reorder Point", format="%d"),
                "safety_stock": st.column_config.NumberColumn("Safety Stock", format="%d"),
                "avg_daily_demand": st.column_config.NumberColumn("Avg Daily Demand", format="%.2f"),
                "std_dev_daily_demand": st.column_config.NumberColumn("Std Dev", format="%.2f"),
                "lead_time_days": st.column_config.NumberColumn("Lead Time (Days)", format="%d"),
                "stock_status": st.column_config.TextColumn("Status")
            },
            hide_index=True,
            use_container_width=True
        )
        
        st.markdown("---")
        st.subheader("Safety Stock vs Current Stock")
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Safety Stock', x=merged_df['product_name'], y=merged_df['safety_stock'], marker_color='green'))
        fig.add_trace(go.Bar(name='Current Stock', x=merged_df['product_name'], y=merged_df['current_stock'], marker_color='blue'))
        fig.add_trace(go.Scatter(name='Reorder Point', x=merged_df['product_name'], y=merged_df['reorder_point'], mode='lines+markers', marker_color='red'))
        fig.update_layout(barmode='group', height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No safety stock data available")

# ==================== STOCKOUT RISK SECTION ====================
elif page == "🚨 Stockout Risk":
    st.title("🚨 Stockout Risk Analysis")
    st.markdown("---")
    
    if data["stockout"]:
        stockout_df = pd.DataFrame(data["stockout"])
        
        if not stockout_df.empty:
            st.metric("Products at Immediate Risk", len(stockout_df))
            
            st.markdown("---")
            st.subheader("Stockout Risk Details")
            st.dataframe(
                stockout_df,
                column_config={
                    "product_name": st.column_config.TextColumn("Product Name"),
                    "current_stock": st.column_config.NumberColumn("Current Stock", format="%d"),
                    "predicted_next_n_days": st.column_config.NumberColumn(f"Predicted Demand ({forecast_days} days)", format="%d"),
                    "predicted_remaining_month": st.column_config.NumberColumn("Remaining Month Demand", format="%d"),
                    "days_left_in_month": st.column_config.NumberColumn("Days Left", format="%d"),
                    "recommended_restock": st.column_config.NumberColumn("Recommended Restock", format="%d")
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.markdown("---")
            st.subheader("Stock vs Demand Comparison")
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Current Stock', x=stockout_df['product_name'], y=stockout_df['current_stock'], marker_color='green'))
            fig.add_trace(go.Bar(name=f'Predicted Demand ({forecast_days}d)', x=stockout_df['product_name'], y=stockout_df['predicted_next_n_days'], marker_color='red'))
            fig.update_layout(barmode='group', height=450)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("✅ No products at immediate stockout risk!")
    else:
        st.info("No stockout risk data available")

# ==================== RESTOCK MANAGEMENT SECTION ====================
elif page == "🔄 Restock Management":
    st.title("🔄 Restock Management")
    st.markdown("---")
    
    if data["restock"]:
        restock_df = pd.DataFrame(data["restock"])
        at_risk_df = restock_df[restock_df['recommended_order_qty'] > 0]
        
        st.metric("Products Needing Restock", len(at_risk_df))
        st.metric("Total Units Needed", sum(at_risk_df['recommended_order_qty']) if not at_risk_df.empty else 0)
        
        st.markdown("---")
        st.subheader("Restock Recommendations")
        
        if not at_risk_df.empty:
            def highlight_risk(row):
                if row['recommended_order_qty'] > 0:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
            
            styled_df = at_risk_df.style.apply(highlight_risk, axis=1)
            st.dataframe(
                styled_df,
                column_config={
                    "product_name": st.column_config.TextColumn("Product Name"),
                    "current_stock": st.column_config.NumberColumn("Current Stock", format="%d"),
                    "reorder_point": st.column_config.NumberColumn("Reorder Point", format="%d"),
                    "recommended_order_qty": st.column_config.NumberColumn("Recommended Order Qty", format="%d"),
                    f"forecasted_demand_next_{forecast_days}days": st.column_config.NumberColumn(f"Forecasted Demand ({forecast_days} days)", format="%d"),
                    "safety_stock": st.column_config.NumberColumn("Safety Stock", format="%d")
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.markdown("---")
            st.subheader("🔄 Bulk Restock Action")
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.info(f"Ready to restock {len(at_risk_df)} products with total quantity: {sum(at_risk_df['recommended_order_qty'])} units")
            
            with col2:
                if st.button("Apply All Restocks", type="primary", use_container_width=True):
                    with st.spinner("Processing bulk restock..."):
                        bulk_items = [
                            {"product_name": row["product_name"], "quantity_added": row["recommended_order_qty"]}
                            for _, row in at_risk_df.iterrows()
                        ]
                        
                        try:
                            response = requests.post(f"{API_URL}/bulk-restock", json={"items": bulk_items})
                            
                            if response.status_code == 200:
                                result = response.json()
                                st.success(f"✅ {result['message']}")
                                if result['updated_products']:
                                    st.json(result['updated_products'])
                                if result['errors']:
                                    st.warning("Some errors occurred:")
                                    st.json(result['errors'])
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Error: {response.text}")
                        except Exception as e:
                            st.error(f"Failed: {str(e)}")
        else:
            st.success("✅ No products need restocking right now!")
    else:
        st.info("No restock data available")

# ==================== MID-MONTH PREDICTION SECTION ====================
elif page == "📅 Mid-Month Prediction":
    st.title("� Mid-Month Stockout Prediction")
    st.markdown("---")
    
    if data["mid_month"]:
        mid_month_df = pd.DataFrame(data["mid_month"])
        
        if not mid_month_df.empty:
            high_risk = len(mid_month_df[mid_month_df['urgency'] == 'High'])
            st.metric("Products with High Urgency", high_risk)
            
            st.markdown("---")
            st.subheader("Expected Stockout Timeline")
            st.dataframe(
                mid_month_df,
                column_config={
                    "product_name": st.column_config.TextColumn("Product Name"),
                    "current_stock": st.column_config.NumberColumn("Current Stock", format="%d"),
                    "predicted_remaining_month_demand": st.column_config.NumberColumn("Remaining Demand", format="%d"),
                    "days_left_in_month": st.column_config.NumberColumn("Days Left", format="%d"),
                    "expected_stockout_date": st.column_config.TextColumn("Expected Stockout Date"),
                    "days_until_stockout": st.column_config.NumberColumn("Days Until Stockout", format="%d"),
                    "urgency": st.column_config.TextColumn("Urgency Level")
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.markdown("---")
            st.subheader("Urgency Distribution")
            urgency_counts = mid_month_df['urgency'].value_counts()
            fig = px.pie(values=urgency_counts.values, names=urgency_counts.index, title="Stockout Urgency Levels")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("✅ No products expected to stockout this month!")
    else:
        st.info("No mid-month prediction data available")

# ==================== UPLOAD SALES SECTION ====================
elif page == "📤 Upload Sales":
    st.title("📤 Upload Sales Data")
    st.markdown("---")
    
    st.subheader("Upload Sales CSV File")
    st.write("Upload your sales data in CSV format. The file should contain: `product_name`, `date`, and `units_sold` columns.")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a CSV file with sales data"
    )
    
    if uploaded_file is not None:
        try:
            # Read the CSV file
            df = pd.read_csv(uploaded_file)
            
            # Display preview of uploaded data
            st.subheader("📋 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Validate required columns
            required_columns = ['product_name', 'date', 'units_sold']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
                st.write("Required columns: `product_name`, `date`, `units_sold`")
            else:
                st.success(f"✅ File uploaded successfully! Found {len(df)} records.")
                
                # Data statistics
                st.subheader("📊 Data Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Records", len(df))
                
                with col2:
                    st.metric("Unique Products", df['product_name'].nunique())
                
                with col3:
                    st.metric("Total Units Sold", df['units_sold'].sum())
                
                # Date range
                df['date'] = pd.to_datetime(df['date'])
                st.subheader("📅 Date Range")
                st.write(f"From: {df['date'].min().date()} To: {df['date'].max().date()}")
                
                # Sales by product
                st.subheader("📈 Sales by Product")
                product_sales = df.groupby('product_name')['units_sold'].sum().sort_values(ascending=False)
                fig = px.bar(product_sales, title="Total Sales by Product")
                st.plotly_chart(fig, use_container_width=True)
                
                # Upload to backend
                st.subheader("🔄 Upload to Database")
                if st.button("Upload Sales Data to Backend", type="primary", use_container_width=True):
                    with st.spinner("Uploading sales data to backend..."):
                        try:
                            # Prepare data for API
                            sales_data = df.to_dict('records')
                            
                            # Send to backend
                            response = requests.post(
                                f"{API_URL}/upload-sales",
                                json={"sales_data": sales_data}
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                st.success(f"✅ {result['message']}")
                                if result.get('uploaded_count'):
                                    st.info(f"📊 Successfully uploaded {result['uploaded_count']} sales records.")
                            else:
                                st.error(f"❌ Error uploading data: {response.text}")
                        except Exception as e:
                            st.error(f"❌ Failed to upload: {str(e)}")
                
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")
    
    # Sample data format
    st.markdown("---")
    st.subheader("📝 Sample Data Format")
    sample_data = pd.DataFrame({
        'product_name': ['milk', 'bread', 'eggs'],
        'date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'units_sold': [50, 100, 30]
    })
    st.dataframe(sample_data, hide_index=True, use_container_width=True)
    
    st.write("💡 **Tip:** Make sure your CSV file has exactly these column names and valid date format (YYYY-MM-DD).")

# ==================== CHATBOT SECTION ====================
elif page == "🤖 AI Chatbot":
    st.title("🤖 Supply Chain Assistant")
    st.markdown("---")
    
    # Initialize chatbot
    if 'chatbot' not in st.session_state:
        from app.services.chatbot import ChatBot
        st.session_state.chatbot = ChatBot(API_URL)
    
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "Hello! I'm your supply chain assistant. I can help you with inventory, forecasts, restocking, and more. Ask me anything!"}
        ]
    
    # Display chat messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    user_input = st.chat_input("Ask me about inventory, forecasts, restocking...")
    
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        with st.spinner("Thinking..."):
            result = st.session_state.chatbot.process_query(user_input)
            bot_response = result["response"]
        
        st.session_state.chat_messages.append({"role": "assistant", "content": bot_response})
        st.rerun()
    
    # Chat controls
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Clear Conversation", use_container_width=True):
            st.session_state.chat_messages = [
                {"role": "assistant", "content": st.session_state.chatbot.clear_conversation()}
            ]
            st.rerun()
    
    with col2:
        if st.button("Show Capabilities", use_container_width=True):
            capabilities = st.session_state.chatbot.get_capabilities()
            st.info(capabilities)
    
    with col3:
        if st.button("Conversation Summary", use_container_width=True):
            summary = st.session_state.chatbot.get_conversation_summary()
            st.info(summary)

# Footer for all pages
st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
