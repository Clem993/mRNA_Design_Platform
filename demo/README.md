# mRNA Design Studio — Demo Database

This directory contains demo databases for testing the import functionality.

## PostgreSQL Demo (Recommended)

A containerized PostgreSQL database with realistic mRNA sequence data.

### Start the Database

```bash
cd demo
docker-compose up -d
```

Wait a few seconds for the database to initialize, then verify it's running:

```bash
docker-compose ps
```

### Connection Details

- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `mrna_studio`
- **User**: `demo_user`
- **Password**: `demo_pass_2024`

### Connect in the App

1. Open the app at http://localhost:5007
2. Click **"⊕  Import Database"** in the sidebar
3. Select **"PostgreSQL"** as backend
4. Enter the connection details above
5. Click **Connect**
6. Select the `mrna_sequences` table
7. Click **Preview** to see the data
8. Map columns (auto-suggestions should work)
9. Click **Import Records**

### Stop the Database

```bash
cd demo
docker-compose down
```

To remove all data:

```bash
docker-compose down -v
```

---

## SQLite Demo (Simple Alternative)

A local file-based database. No server required.

### Create the Database

```bash
python demo/create_demo_db.py
```

### Connection Details

- **Backend**: SQLite
- **File Path**: `/Users/nicholasjustice/repos/mrna_design_studio/demo/mrna_parts.db`

---

## Demo Data Contents

### mrna_sequences Table (4 records)

1. **eGFP-hBG-UTRs** - Component-based (separate 5'UTR, CDS, 3'UTR, poly-A)
2. **mCherry-AlbUTR** - Component-based with Albumin 3'UTR
3. **eGFP-full-v2** - Monolithic (entire mRNA in `full_mrna` field)
4. **mCherry-full** - Monolithic with EMCV IRES

The mix demonstrates how SchemaMapper handles different database schemas.

### plasmid_backbones Table (1 record)

1. **pUC19-MCS** - Classic E. coli cloning vector
