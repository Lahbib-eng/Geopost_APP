import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Geopost Dashboard", layout="wide", page_icon="📦")
RED = "#DC0032"   # Geopost color

st.title("📦 Geopost — Customer Activity Dashboard")

# ---------- LOAD ----------
@st.cache_data
def load():
    df = pd.read_csv('data_with_groups.csv', sep=';', dtype={'CD_CUSTOMER':str})
    df['PERIOD'] = pd.to_datetime(df['PERIOD'])
    ref = pd.read_csv('updated_REF_GROUP.txt', sep=';')
    fc = pd.read_csv('forecast_6months.csv', sep=';'); fc['PERIOD'] = pd.to_datetime(fc['PERIOD'])
    clf = pd.read_csv('group_classification.csv', sep=';')
    return df, ref, fc, clf

df, ref, fc, clf = load()

# add vertical/subvertical (df already has GroupName)
df = df.merge(ref[['GroupeCode','VerticalMarket','SubVerticalMarket']],
              left_on='GroupCode', right_on='GroupeCode', how='left')

# operator codes -> readable country names
country_map = {'BE':'Belgium','BG':'Bulgaria','BR':'Brazil','CH':'Switzerland','CZ':'Czechia',
    'DE':'Germany','EE':'Estonia','ES':'Spain','FR':'France','GB':'United Kingdom',
    'HR':'Croatia','HU':'Hungary','IE':'Ireland','IT':'Italy','LT':'Lithuania','LV':'Latvia',
    'NL':'Netherlands','PL':'Poland','PT':'Portugal','RO':'Romania','SI':'Slovenia','SK':'Slovakia'}
df['Country'] = df['CD_FILE_OPERATOR'].str[:2].map(country_map)

# clusters -> business labels
cluster_names = {0:"Volume giants", 1:"Light shippers", 2:"Heavy shippers", 3:"Mega shippers"}
clf['client_type'] = clf['cluster'].map(cluster_names).fillna("Other")

# ---------- FILTERS ----------
st.sidebar.header("🔎 Filters")
groups  = st.sidebar.multiselect("Central group", sorted(df.GroupName.dropna().unique()))
country = st.sidebar.multiselect("Country", sorted(df.Country.dropna().unique()))
vert    = st.sidebar.multiselect("Vertical market", sorted(df.VerticalMarket.dropna().unique()))
subv    = st.sidebar.multiselect("Sub-vertical", sorted(df.SubVerticalMarket.dropna().unique()))
dmin, dmax = df.PERIOD.min(), df.PERIOD.max()
period = st.sidebar.date_input("Period", [dmin, dmax], min_value=dmin, max_value=dmax)

d = df.copy()
if groups:  d = d[d.GroupName.isin(groups)]
if country: d = d[d.Country.isin(country)]
if vert:    d = d[d.VerticalMarket.isin(vert)]
if subv:    d = d[d.SubVerticalMarket.isin(subv)]
if len(period)==2:
    d = d[(d.PERIOD>=pd.to_datetime(period[0]))&(d.PERIOD<=pd.to_datetime(period[1]))]

# ================= TABS =================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Forecast", "🏢 Client types", "🔗 Groups & subsidiaries"])

# ---------- TAB 1 : OVERVIEW ----------
with tab1:
    st.subheader("Key figures")
    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue", f"{d.TurnoverDomestic_EUR.sum()/1e6:.0f} M€")
    c2.metric("Parcels", f"{int(d.ParcelsDomestic.sum()):,}".replace(',', ' '))
    c3.metric("Active groups", d.GroupName.nunique())

    st.subheader("Monthly revenue")
    ts = d.groupby('PERIOD')['TurnoverDomestic_EUR'].sum().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ts.PERIOD, y=ts.TurnoverDomestic_EUR, line=dict(color=RED)))
    fig.update_layout(height=300, yaxis_title="Revenue (€)")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Revenue by country")
        pc = d.groupby('Country')['TurnoverDomestic_EUR'].sum().sort_values().reset_index()
        st.plotly_chart(px.bar(pc, x='TurnoverDomestic_EUR', y='Country', orientation='h',
                        color_discrete_sequence=[RED], height=400,
                        labels={'TurnoverDomestic_EUR':'Revenue (€)'}), use_container_width=True)
    with col2:
        st.subheader("Revenue by vertical")
        vc = d.groupby('VerticalMarket')['TurnoverDomestic_EUR'].sum().sort_values().reset_index()
        st.plotly_chart(px.bar(vc, x='TurnoverDomestic_EUR', y='VerticalMarket', orientation='h',
                        color_discrete_sequence=[RED], height=400,
                        labels={'TurnoverDomestic_EUR':'Revenue (€)'}), use_container_width=True)
        
        # ---------- TAB 2 : FORECAST ----------
with tab2:
    st.subheader("Next 6 months forecast")
    show_forecast = not (groups or country or vert or subv)
    if show_forecast:
        c1, c2 = st.columns(2)
        c1.metric("Forecast revenue (6 mo)", f"{fc.CA_prevu_EUR.sum()/1e6:.0f} M€")
        c2.metric("Forecast parcels (6 mo)", f"{int(fc.Colis_prevu.sum()):,}".replace(',', ' '))

        ts = d.groupby('PERIOD')['TurnoverDomestic_EUR'].sum().reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ts.PERIOD, y=ts.TurnoverDomestic_EUR, name="History", line=dict(color=RED)))
        fig.add_trace(go.Scatter(x=fc.PERIOD, y=fc.CA_prevu_EUR, name="Forecast", line=dict(color="#888", dash='dash')))
        fig.update_layout(height=350, yaxis_title="Revenue (€)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Aggregate-level forecast (seasonal Holt-Winters model, ~5% error).")
    else:
        st.info("Forecast is shown at the global level. Remove filters to see it.")

# ---------- TAB 3 : CLIENT TYPES ----------
with tab3:
    st.subheader("Our client types")
    st.caption("Each bubble = a group · Size = revenue · Color = client type")
    fig = px.scatter(clf, x='kg_per_parcel', y='rev_per_parcel', size='revenue',
                     color='client_type', text='GroupName', height=520,
                     labels={'kg_per_parcel':'Weight per parcel (kg)',
                             'rev_per_parcel':'Value per parcel (€)', 'client_type':'Client type'})
    fig.update_traces(textposition='top center')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("""
    **How to read this:**
    - **Volume giants** — huge numbers of light, low-value parcels (fashion, marketplace)
    - **Light shippers** — light parcels, mid-sized activity (cosmetics, electronics)
    - **Heavy shippers** — heavy parcels (DIY, meal kits, books)
    - **Mega shippers** — very high volume and weight (HelloFresh, Zooplus)
    """)
 # ---------- TAB 4 : GROUPS & SUBSIDIARIES ----------
with tab4:
    st.subheader("Groups and their subsidiaries")
    grp = st.selectbox("Select a group", sorted(df[df.GroupCode!=99].GroupName.dropna().unique()))

    # table of accounts
    subs = (df[df.GroupName==grp][['CD_CUSTOMER','LB_CUST_NAME_1','Country']]
            .drop_duplicates().sort_values('Country'))
    st.write(f"**{len(subs)} accounts linked to {grp}**")
    st.dataframe(subs, use_container_width=True, height=300)

    # network graph
    st.subheader("Network view")
    from pyvis.network import Network
    import streamlit.components.v1 as components

    net = Network(height="450px", width="100%", bgcolor="#ffffff", font_color="#333")
    net.add_node(grp, label=grp, color=RED, size=30, shape="star")
    for _, r in subs.iterrows():
        name = str(r.LB_CUST_NAME_1)[:22]
        net.add_node(r.CD_CUSTOMER, label=name, color="#2a78d6", size=10)
        net.add_edge(grp, r.CD_CUSTOMER)
    net.save_graph("graph.html")
    with open("graph.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=470)
