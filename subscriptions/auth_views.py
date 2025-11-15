from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm

def signup(request):
    """
    Vue d'inscription (signup). Crée un nouvel utilisateur avec le formulaire
    UserCreationForm (username + password1 + password2).
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Compte créé avec succès. Vous pouvez maintenant vous connecter.")
            return redirect('subscriptions:login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})