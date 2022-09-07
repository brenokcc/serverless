from orm import Model


class Pessoa(Model):
    pass


if __name__ == '__main__':
    # COUNTING OBJECTS
    # print(Pessoa.objects.count())

    # LISTING ALL OBJECTS
    # Pessoa.objects.query()
    # qs = Pessoa.objects.all()
    # for obj in qs:
    #     print(type(obj), obj)

    # ADDING AN OBJECT
    # obj = Pessoa.objects.create(nome='Carlos Breno', contato=dict(email='brenokcc@yahoo.com.br'))
    # print(obj['pk'])

    # GETTING AND UPDATING AN OBJECT
    # obj = Pessoa.objects.get(pk='f51d7a4c2ac611ed8f6f3c15c2da2c92')
    # print(obj)
    # obj['idade'] = 38
    # obj.save()
    # obj2 = Pessoa.objects.get(pk='f51d7a4c2ac611ed8f6f3c15c2da2c92')
    # print(obj2)

    # FILTERING EXISTING OBJECT
    # qs = Pessoa.objects.filter(contato__email='brenokcc@yahoo.com.br2')
    # print(qs)
    # obj = qs.first()
    # print(obj)

    # FILTERING INEXISTING OBJECT
    # obj = Pessoa.objects.filter(contato__email='brenokcc@yahoo.com.brr').first()
    # print(obj)

    # FETCHING SPECIFIC VALUES
    # print(Pessoa.objects.all().values('nome', 'idade'))
    # print(Pessoa.objects.all().values_list('nome', 'idade'))
    # print(Pessoa.objects.all().values_list('nome', flat=True))

    # ADDING AND DELETING AN OBJECT
    # obj = Pessoa.objects.create(nome='Juca da Silva', contato=dict(email='juca@mail.com'))
    # print(Pessoa.objects.all().values('id', 'nome'))
    # obj.delete()
    # print(Pessoa.objects.all().values('id', 'nome'))

    # DELETING ALL OBJECTS
    # Pessoa.objects.create(nome='Juca da Silva')
    # Pessoa.objects.create(nome='Maria da Silva')
    # print(Pessoa.objects.all().values('id', 'nome'))
    # Pessoa.objects.delete()
    # print(Pessoa.objects.all().values('id', 'nome'))

    # USING MULTIPLE FILTERS
    # Pessoa.objects.create(nome='Juca da Silva', sexo='M', idade=23)
    # Pessoa.objects.create(nome='Maria da Silva', sexo='F', idade=18)
    # Pessoa.objects.create(nome='Gabriel da Silva', sexo='M', idade=30)
    # print(Pessoa.objects.all())
    # qs1 = Pessoa.objects.filter(sexo='M')
    # qs2 = Pessoa.objects.filter(sexo='F')
    # qs3 = (qs1 | qs2).exclude(idade__lte=20)
    # print(qs1.query)
    # print(qs2.query)
    # print(qs3.query)
    # print(qs3.values_list('nome', flat=True))
    # qs4 = (Pessoa.objects.filter(idade__lte=20) | Pessoa.objects.filter(idade__gte=30)).exclude(sexo='M')
    # print(qs4.query)
    # print(qs4.values_list('nome', flat=True))

    pks = ['9825fa7e2ae611ed97953c15c2da2c92', '9837de882ae611ed97953c15c2da2c92']
    # Pessoa.objects.fetch(pks)
    Pessoa.objects.filter2()
    # print(Pessoa.objects.all())
    pass