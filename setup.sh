#!/bin/bash
# ============================================================
#  VisaTrack — Script d'installation automatique
#  Usage : bash setup.sh
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "  ██╗   ██╗██╗███████╗ █████╗ ████████╗██████╗  █████╗  ██████╗██╗  ██╗"
echo "  ██║   ██║██║██╔════╝██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝"
echo "  ██║   ██║██║███████╗███████║   ██║   ██████╔╝███████║██║     █████╔╝ "
echo "  ╚██╗ ██╔╝██║╚════██║██╔══██║   ██║   ██╔══██╗██╔══██║██║     ██╔═██╗ "
echo "   ╚████╔╝ ██║███████║██║  ██║   ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗"
echo "    ╚═══╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "${GREEN}  Plateforme SaaS de surveillance de créneaux Visa${NC}"
echo ""

# ── Vérification Python ──────────────────────────────────────
echo -e "${YELLOW}[1/7] Vérification de Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 non trouvé. Installez Python 3.11+ depuis python.org${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓ Python $PYTHON_VERSION détecté${NC}"

# ── Environnement virtuel ────────────────────────────────────
echo -e "${YELLOW}[2/7] Création de l'environnement virtuel...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Environnement virtuel créé${NC}"
else
    echo -e "${GREEN}✓ Environnement virtuel existant trouvé${NC}"
fi

# Activer le venv
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# ── Installation des dépendances ─────────────────────────────
echo -e "${YELLOW}[3/7] Installation des dépendances Python...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dépendances installées${NC}"

# ── Fichier .env ─────────────────────────────────────────────
echo -e "${YELLOW}[4/7] Configuration de l'environnement...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Fichier .env créé depuis .env.example${NC}"
    echo -e "${YELLOW}  ⚠ Pensez à remplir vos clés API dans le fichier .env${NC}"
else
    echo -e "${GREEN}✓ Fichier .env existant conservé${NC}"
fi

# ── Dossier logs ─────────────────────────────────────────────
mkdir -p logs media staticfiles

# ── Migrations ───────────────────────────────────────────────
echo -e "${YELLOW}[5/7] Création de la base de données...${NC}"
python manage.py makemigrations --noinput
python manage.py migrate --noinput
echo -e "${GREEN}✓ Base de données initialisée${NC}"

# ── Données initiales ────────────────────────────────────────
echo -e "${YELLOW}[6/7] Chargement des données initiales...${NC}"
python manage.py shell -c "
from apps.monitoring.models import Country, VisaCenter

countries_data = [
    ('FR', 'France', '🇫🇷'), ('ES', 'Espagne', '🇪🇸'),
    ('DE', 'Allemagne', '🇩🇪'), ('IT', 'Italie', '🇮🇹'),
    ('CA', 'Canada', '🇨🇦'), ('PT', 'Portugal', '🇵🇹'),
    ('BE', 'Belgique', '🇧🇪'), ('NL', 'Pays-Bas', '🇳🇱'),
]
for code, name, flag in countries_data:
    Country.objects.get_or_create(code=code, defaults={'name_fr': name, 'name_en': name, 'flag_emoji': flag})

print('✓ Pays créés')

france = Country.objects.get(code='FR')
espagne = Country.objects.get(code='ES')
canada  = Country.objects.get(code='CA')

centers = [
    ('BLS', espagne, 'Dakar',   'https://blsspainsenegal.com'),
    ('TLS', france,  'Dakar',   'https://fr.tlscontact.com/visa/SN/fr'),
    ('TLS', france,  'Abidjan', 'https://fr.tlscontact.com/visa/CI/fr'),
    ('VFS', canada,  'Dakar',   'https://www.vfsglobal.ca/canada/senegal'),
]
for plat, country, city, url in centers:
    VisaCenter.objects.get_or_create(
        platform=plat, country=country, city=city,
        defaults={'url_booking': url, 'check_interval': 5}
    )
print('✓ Centres visa créés')
" 2>/dev/null
echo -e "${GREEN}✓ Données initiales chargées${NC}"

# ── Superuser ────────────────────────────────────────────────
echo -e "${YELLOW}[7/7] Création du compte administrateur...${NC}"
python manage.py createsuperuser --noinput \
    --email admin@visatrack.app 2>/dev/null || true

python manage.py shell -c "
from apps.users.models import User
if not User.objects.filter(email='admin@visatrack.app').exists():
    User.objects.create_superuser(
        email='admin@visatrack.app',
        full_name='Administrateur VisaTrack',
        password='Admin@1234',
        role='superadmin',
    )
    print('✓ Admin créé : admin@visatrack.app / Admin@1234')
else:
    print('✓ Admin existant conservé')
" 2>/dev/null

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ VisaTrack installé avec succès !${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Lancer le serveur :${NC}"
echo -e "  ${YELLOW}python manage.py runserver${NC}"
echo ""
echo -e "  ${BLUE}URLs disponibles :${NC}"
echo -e "  • Application   : ${YELLOW}http://localhost:8000${NC}"
echo -e "  • Admin Django  : ${YELLOW}http://localhost:8000/admin${NC}"
echo -e "  • API Docs      : ${YELLOW}http://localhost:8000/api/docs${NC}"
echo ""
echo -e "  ${BLUE}Compte admin :${NC}"
echo -e "  • Email    : ${YELLOW}admin@visatrack.app${NC}"
echo -e "  • Password : ${YELLOW}Admin@1234${NC}"
echo ""
echo -e "  ${BLUE}Prochaine étape — configurer vos clés API dans .env :${NC}"
echo -e "  ${YELLOW}nano .env${NC}  (ou ouvrez le fichier dans votre éditeur)"
echo ""
