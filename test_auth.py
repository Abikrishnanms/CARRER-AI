from auth.auth_utils import signup_user, login_user

print(signup_user("testuser", "test@example.com", "mypassword123", "Test User", "Kerala"))
print(login_user("testuser", "mypassword123"))
print(login_user("testuser", "wrongpassword"))