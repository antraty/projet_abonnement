from django.contrib.auth.decorators import login_required
from django.urls import path
from . import views
from . import auth_views as local_auth_views
from django.contrib.auth import views as auth_views
from .views import send_daily_report_view, expire_alerts_view


app_name = 'subscriptions'

urlpatterns = [

    # Vue publiques
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    path('signup/', local_auth_views.signup, name='signup'),

    # Vues protégées
    path('', login_required(views.dashboard), name='dashboard'),
    path('mail/',login_required(send_daily_report_view),name='mail'),
    path('expire/',login_required(expire_alerts_view), name='expire'),
    path('clients/', login_required(views.client_list), name='client_list'),
    path('clients/nouveau/', login_required(views.client_create), name='client_create'),
    path('clients/<int:pk>/modifier/', login_required(views.client_edit), name='client_edit'),
    path('clients/<int:pk>/supprimer/', login_required(views.client_delete), name='client_delete'),
    path('clients/export/csv/', login_required(views.export_clients_csv), name='export_clients_csv'),
    path('clients/export/pdf/', login_required(views.export_clients_pdf), name='export_clients_pdf'),
    path('abonnements/', login_required(views.subscription_list), name='subscription_list'),
    path('abonnements/nouveau/', login_required(views.subscription_create), name='subscription_create'),
    path('abonnements/<int:pk>/modifier/', login_required(views.subscription_edit), name='subscription_edit'),
    path('abonnements/<int:pk>/supprimer/', login_required(views.subscription_delete), name='subscription_delete'),
    path('abonnements/export/csv/', login_required(views.export_subscriptions_csv), name='export_subscriptions_csv'),
    path('abonnements/<int:pk>/relancer/', login_required(views.subscription_renew), name='subscription_renew'),
    path('abonnements/export/pdf/', login_required(views.export_subscriptions_pdf), name='export_subscriptions_pdf'),
]
