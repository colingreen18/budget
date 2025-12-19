from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # for signup

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='budget/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('categories/', views.category_list, name="categories"),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
]

