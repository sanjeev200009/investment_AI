-- Create a function to handle user synchronisation
create or replace function public.handle_new_user() 
returns trigger as $$
begin
  -- 1. Insert into our public.users table
  insert into public.users (user_id, email, password_hash, role)
  values (
    new.id, 
    new.email, 
    'supabase-managed', -- Password is managed by Supabase
    'user'
  );

  -- 2. Insert a default profile into public.user_profiles
  insert into public.user_profiles (user_id, full_name)
  values (
    new.id, 
    coalesce(new.raw_user_meta_data->>'full_name', 'InvestAI User')
  );

  return new;
end;
$$ language plpgsql security definer;

-- Create the trigger that runs the function every time a user signs up
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
