from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # for signup

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='budget/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.dashboard, name='dashboard'),

    # Categories
    path('categories/', views.category_list, name="category_list"),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('category/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/add/', views.transaction_create, name='transaction_create'),
    path('transactions/<int:pk>/edit/', views.transaction_update, name='transaction_update'),
    path('transaction/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),

    # Stores
    path('stores/', views.store_list, name='store_list'),
    path('stores/add/', views.store_create, name='store_create'),
    path('store/<int:pk>/edit/', views.store_update, name='store_update'),
    path('store/<int:pk>/delete/', views.store_delete, name='store_delete'),

    # Profile
    path('profile/', views.profile, name='profile'),

    # Insights
    path('insights/', views.insights, name='insights'),
]

