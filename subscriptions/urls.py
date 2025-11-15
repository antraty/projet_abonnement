from django.urls import path
from . import views
from . import auth_views as local_auth_views
from django.contrib.auth import views as auth_views

app_name = 'subscriptions'

urlpatterns = [
    
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    path('signup/', local_auth_views.signup, name='signup'),

   
    path('', views.dashboard, name='dashboard'),
    path('clients/', views.client_list, name='client_list'),
    path('clients/nouveau/', views.client_create, name='client_create'),
    path('clients/<int:pk>/modifier/', views.client_edit, name='client_edit'),
    path('clients/<int:pk>/supprimer/', views.client_delete, name='client_delete'),
    path('clients/export/csv/', views.export_clients_csv, name='export_clients_csv'),
    path('clients/export/pdf/', views.export_clients_pdf, name='export_clients_pdf'),
    path('abonnements/', views.subscription_list, name='subscription_list'),
    path('abonnements/nouveau/', views.subscription_create, name='subscription_create'),
    path('abonnements/<int:pk>/modifier/', views.subscription_edit, name='subscription_edit'),
    path('abonnements/<int:pk>/supprimer/', views.subscription_delete, name='subscription_delete'),
    path('abonnements/export/csv/', views.export_subscriptions_csv, name='export_subscriptions_csv'),
    path('abonnements/<int:pk>/relancer/', views.subscription_renew, name='subscription_renew'),
    path('abonnements/export/pdf/', views.export_subscriptions_pdf, name='export_subscriptions_pdf'),
]