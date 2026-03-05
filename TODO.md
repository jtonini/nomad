# NØMAD Project - Task List

*Last updated: February 25, 2026*

---

## ✅ Completed

### Paper (JORS)
- [x] Paper accepted and submitted
- [x] High-res figures uploaded (PNG format)
- [x] Text flow improvements throughout
- [x] Architecture diagram updated with 7 components
- [x] CV% explanation added
- [x] Figure references fixed

### Package/Release
- [x] PyPI v1.2.4 live with all features
- [x] `--db` option fixed for dashboard
- [x] Trusted publishing configured for nomad-hpc
- [x] Old `nomade` package archived
- [x] README updated with new features

### Dashboard
- [x] Light/dark theme with logo switching
- [x] Workstation monitoring
- [x] Storage monitoring
- [x] Interactive sessions view
- [x] NØMAD branding (cyan + rusty red Ø)

---

## 📋 To Do

### 🎨 Website (nomad-hpc.com)
- [ ] Update typography to modern sans-serif (Inter, DM Sans, or Satoshi)

### 📝 Documentation
- [ ] Document `nomad readiness` command
- [ ] Document `nomad diag` commands
- [ ] Document workstation/storage monitoring

### 🔧 Technical
- [ ] Add CI testing workflow to GitHub Actions

### 💼 Business
- [ ] Register LLC
- [ ] File USPTO trademark

---

## 🖥️ GUI Project (Future - Private Repo)

### Business Model
```
┌─────────────────────────────────────────────────────────────────┐
│                        NØMAD Ecosystem                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   FREE (Open Source - GitHub)                                   │
│   • CLI tool                                                    │
│   • Web dashboard                                               │
│   • All core features                                           │
│   • Community support                                           │
│   • AGPL license                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   PAID: GUI License                                             │
│   • Desktop/Web GUI application                                 │
│   • Multi-cluster management                                    │
│   • All CLI features in intuitive UI                            │
│   • Activity log (SQLite-based, ~5s refresh)                    │
│   • Email support                                               │
│   • Per-seat or site license                                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   PAID: GUI + Support Tier                                      │
│   • Everything in GUI License                                   │
│   • Real-time collaboration server setup                        │
│   • Server hosted by customer (you assist setup)                │
│   • Priority support                                            │
│   • Custom integrations                                         │
│   • Training sessions                                           │
│   • SLA                                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture by Tier

**GUI License (Base):**
```
┌─────────┐         SSH          ┌───────────┐
│  GUI    │ ◄──────────────────► │  Cluster  │
└─────────┘                      │  + SQLite │
                                 │  activity │
(Lightweight, no server)         └───────────┘
```

**GUI + Support Tier:**
```
┌─────────┐                      ┌───────────────────┐
│  GUI    │ ◄─────WebSocket────► │  Customer's       │
│ (users) │                      │  Server           │
└─────────┘                      │  (you help setup) │
                                 └─────────┬─────────┘
                                           │
                                     ┌─────┴─────┐
                                     │  Clusters │
                                     └───────────┘
```

### Key Points
- You don't host anything - customers own their infrastructure
- GUI is always paid - not free
- Server is optional - part of higher support tier
- Server setup assistance - included in support, not a separate product
- NØMAD includes server code - but deploying it is a support service

### Development Phases

**Phase 1: GUI with SQLite Activity**
- React + Tailwind + FastAPI
- Connects directly to clusters via SSH
- Activity log in SQLite (polling ~5s)
- No external server needed
- Private repo

**Phase 2: Desktop Wrapper (Tauri)**
- Native app (~5MB)
- System tray, notifications
- Win/Mac/Linux

**Phase 3: Real-Time Server (Support Tier)**
- Code included in NØMAD
- Customer deploys on their infrastructure
- Setup assistance as part of support tier
- WebSocket-based presence & activity

### GUI Features
- Server registration & management
- All CLI commands via UI:
  - `nomad init` → Setup wizard
  - `nomad collect` → Start/stop collectors
  - `nomad dashboard` → Embedded dashboard view
  - `nomad readiness` → Data readiness panel
  - `nomad diag` → Diagnostics panel
  - `nomad edu` → Educational analytics views
  - `nomad predict` → ML predictions
  - `nomad alerts` → Alert management
  - `nomad community` → Export/preview
- Multi-server management
- Settings & configuration UI
- SSH tunnel management

### Tech Stack
- Frontend: React + Tailwind CSS + shadcn/ui
- Backend: FastAPI (extends existing)
- Desktop: Tauri (Rust)
- Auth: JWT or OAuth
- DB: SQLite (local) or PostgreSQL (server tier)
