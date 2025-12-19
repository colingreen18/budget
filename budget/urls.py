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

    # Transactions
    path('transactions/add/', views.transaction_create, name='transaction_create'),
    # Optional later: edit and list views
    # path('transactions/<int:pk>/edit/', views.transaction_update, name='transaction_update'),
    # path('transactions/', views.transaction_list, name='transaction_list'),
]

