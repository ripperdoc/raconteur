# coding=utf-8

from models import *
from flask_peewee.utils import make_password
from peewee import drop_model_tables, create_model_tables

def altor_date(year, month, day):
    return year*360+(month-1)*30+(day-1)

def setup_models():
    models = [
        SessionPresentUser, 
        Session,
        Scene,
        Campaign,
        ConversationMember,
        GroupMember,
        Message,
        Relationship,
        MediaArticle,
        PersonArticle,
        EventArticle,
        RelationType,
        PlaceArticle,
        ArticleRelation,
        ArticleGroup,
        Group,
        Conversation,
        User,
        Article,
        World]
    drop_model_tables(models, fail_silently=True)
    create_model_tables(models)
    
    mundana = World.create(title="Mundana", publisher="Neogames", description=u"En fantasyvärld för grisodling")
    altor = World.create(title="Altor", publisher=u"Niklas Fröjd", description=u"Drakar Demoner advanced")
    kult = World.create(title="Kult", publisher=u"Äventyrsspel", description=u"Demiurger och nefariter")

    RelationType.create(name="child of")
    RelationType.create(name="parent of")
    RelationType.create(name="friend of")
    RelationType.create(name="enemy of")
    RelationType.create(name="distant relative of")

#mf = User.create(username='admin', password='a', email='ripperdoc@gmail.com', active=True, admin=True, realname='Martin F', description='Always games in a hat. Has a cat.')
    mf = User.create(username='admin', password=make_password('admin'), email='ripperdoc@gmail.com', active=True,
        admin=True, realname='Martin F', description='Always games in a hat. Has a cat.')
    nf = User.create(username='niklas', password=make_password('niklas'), email='user@user.com', active=True,
        admin=False, realname='Niklas F')
    pf = User.create(username='per', password=make_password('per'), email='user@user.com', active=True, admin=False,
        realname='Per F')
    mb = User.create(username='marco', password=make_password('marco'), email='user@user.com', active=True, admin=False,
        realname='Marco B')
    fj = User.create(username='fredrik', password=make_password('fredrik'), email='user@user.com', active=True,
        admin=False, realname='Fredrik J')
    pd = User.create(username='paul', password=make_password('paul'), email='user@user.com', active=True, admin=False,
        realname='Paul D')
    ar = User.create(username='alex', password=make_password('alex'), email='user@user.com', active=True, admin=False,
        realname='Alex R')
    pn = User.create(username='petter', password=make_password('petter'), email='user@user.com', active=True,
        admin=False, realname='Petter N')
    ks = User.create(username='krister', password=make_password('krister'), email='user@user.com', active=True,
        admin=False, realname='Krister S')
    cs = User.create(username='calle', password=make_password('calle'), email='user@user.com', active=True, admin=False,
        realname='Carl-Johan S')
    mj = User.create(username='mattias', password=make_password('mattias'), email='user@user.com', active=True,
        admin=False, realname='Mattias J')
    rl = User.create(username='robin', password=make_password('robin'), email='user@user.com', active=True, admin=False,
        realname='Robin L')
    rj = User.create(username='rikard', password=make_password('rikard'), email='user@user.com', active=True,
        admin=False, realname='Rikard J')
    vs = User.create(username='victoria', password=make_password('victoria'), email='user@user.com', active=True,
        admin=False, realname='Victoria S')
    je = User.create(username='john', password=make_password('john'), email='user@user.com', active=True, admin=False,
        realname='John E')
    ad = User.create(username='anders', password=make_password('anders'), email='user@user.com', active=True,
        admin=False, realname='Anders D')
    jc = User.create(username='johan', password=make_password('johan'), email='user@user.com', active=True, admin=False,
        realname='Johan C')
    cm = User.create(username='claes', password=make_password('claes'), email='user@user.com', active=True, admin=False,
        realname='Claes M')
    dm = User.create(username='daniel', password=make_password('daniel'), email='user@user.com', active=True, admin=False,
        realname='Daniel M')
    jg = User.create(username='jonathan', password=make_password('jonathan'), email='user@user.com', active=True,
        admin=False, realname='Jonathan G')
    User.create(username='user1', password=make_password('user'), email='user@user.com', active=True, admin=False,
        realname='User Userson')
    User.create(username='user2', password=make_password('user'), email='user@user.com', active=True, admin=False,
        realname='User Userson')
    User.create(username='user3', password=make_password('user'), email='user@user.com', active=True, admin=False,
        realname='User Userson')
    User.create(username='user4', password=make_password('user'), email='user@user.com', active=True, admin=False,
        realname='User Userson')
    
    MediaArticle.create(mime_type="image/jpg",
                        url="http://kaigon.se/wiki/images/6/6b/Ljusets_son.jpg",
                        article=Article.create(type=ARTICLE_MEDIA,
                                               title=u"Ljusbringaren",
                                               content=u"No content",
                                               world=altor,
                                               creator=mj))
    PersonArticle.create(born=altor_date(1653,3,4),
                         died=altor_date(1891,12,3),
                         gender=GENDER_MALE,
                         occupation=u"Ljusbringaren",
                         article=Article.create(type=ARTICLE_PERSON,
                                                title=u"Ljusbringaren bild",
                                                content=u"No content",
                                                world=altor,
                                               creator=rl))

    Relationship.create(from_user=mf, to_user=nf)
    Relationship.create(from_user=nf, to_user=mf)
    Relationship.create(from_user=rj, to_user=vs)
    Relationship.create(from_user=mf, to_user=ks)

    Relationship.create(from_user=jc, to_user=nf)
    Relationship.create(from_user=nf, to_user=jc)
    Relationship.create(from_user=pf, to_user=nf)
    Relationship.create(from_user=nf, to_user=pf)
    Relationship.create(from_user=cm, to_user=nf)
    Relationship.create(from_user=nf, to_user=cm)
    Relationship.create(from_user=dm, to_user=nf)
    Relationship.create(from_user=nf, to_user=dm)
    Relationship.create(from_user=pf, to_user=jc)
    Relationship.create(from_user=jc, to_user=pf)
    Relationship.create(from_user=cm, to_user=jc)
    Relationship.create(from_user=jc, to_user=cm)
    Relationship.create(from_user=dm, to_user=jc)
    Relationship.create(from_user=jc, to_user=dm)
    Relationship.create(from_user=cm, to_user=pf)
    Relationship.create(from_user=pf, to_user=cm)
    Relationship.create(from_user=dm, to_user=pf)
    Relationship.create(from_user=pf, to_user=dm)
    Relationship.create(from_user=dm, to_user=cm)
    Relationship.create(from_user=cm, to_user=dm)

    Relationship.create(from_user=ar, to_user=mf)
    Relationship.create(from_user=mf, to_user=ar)
    Relationship.create(from_user=mf, to_user=mb)
    Relationship.create(from_user=mb, to_user=vs)
    Relationship.create(from_user=ar, to_user=mb)

    c1 = Conversation.create()
    c2 = Conversation.create()
    c3 = Conversation.create()
    

    ConversationMember.create(conversation=c1, member=mf)
    ConversationMember.create(conversation=c1, member=nf)
    
    ConversationMember.create(conversation=c2, member=mf)
    ConversationMember.create(conversation=c2, member=mb)
    
    ConversationMember.create(conversation=c3, member=nf)
    ConversationMember.create(conversation=c3, member=ks)

    ng = Group.create(name='Nero', location='Gothenburg', description=u'Liten spelgrupp som gillar pervers humor')
    ng.save()
    mg = Group.create(name='Nemesis', location='Gothenburg', description=u'Test')
    mg.save()
    kg = Group.create(name='Kulthack', location='Gothenburg', description=u'Test')
    kg.save()

    GroupMember.create(group=ng, member=mf, status=GROUP_MASTER).save()
    GroupMember.create(group=mg, member=nf, status=GROUP_MASTER).save()
    GroupMember.create(group=kg, member=rl, status=GROUP_MASTER).save()
    GroupMember.create(group=ng, member=nf, status=GROUP_PLAYER).save()
    GroupMember.create(group=ng, member=ar, status=GROUP_PLAYER).save()
    GroupMember.create(group=ng, member=mb, status=GROUP_PLAYER).save()
    GroupMember.create(group=ng, member=pn, status=GROUP_PLAYER).save()
    GroupMember.create(group=ng, member=pf, status=GROUP_PLAYER).save()
    GroupMember.create(group=ng, member=fj, status=GROUP_PLAYER).save()
    GroupMember.create(group=ng, member=pd, status=GROUP_PLAYER).save()
    GroupMember.create(group=mg, member=jg, status=GROUP_PLAYER).save()
    GroupMember.create(group=mg, member=pn, status=GROUP_PLAYER).save()
    GroupMember.create(group=mg, member=jc, status=GROUP_PLAYER).save()
    GroupMember.create(group=mg, member=pf, status=GROUP_PLAYER).save()
    GroupMember.create(group=mg, member=cm, status=GROUP_PLAYER).save()
    GroupMember.create(group=mg, member=dm, status=GROUP_PLAYER).save()
    GroupMember.create(group=kg, member=mb, status=GROUP_PLAYER).save()
    GroupMember.create(group=kg, member=pn, status=GROUP_PLAYER).save()
    GroupMember.create(group=kg, member=ks, status=GROUP_PLAYER).save()
    
    # Make sure you use unicode strings by prefixing with u''
    Message.create(user=nf, content=u'Hur går det, får jag höja min xp som vi pratade om?', conversation=c1)
    Message.create(user=jg, content=u'Kul spel sist!')
    Message.create(user=vs, content=u'Min karaktär dog, helvete!')
    Message.create(user=ks, content=u'När får jag vara med då?')
    Message.create(user=ar, content=u'Jag tar med ölen')
    Message.create(user=mf, content=u'Visst, inga problem1', conversation=c1)
    Message.create(user=mf, content=u'Vi borde testa raconteur snart!', conversation=c2)
    Message.create(user=mb, content=u'Definitivt!', conversation=c2)
    Message.create(user=nf, content=u'Hallå?', conversation=c3)
    
    scmp = Campaign.create(name=u"Spelveckan", world=mundana, group=ng, rule_system=u"Eon", description=u"Deep drama at the beginning of July each year.")
    cd4k = Campaign.create(name=u"Den Fjärde Konfluxen", world=altor, group=mg, rule_system=u"Drakar & Demoner", description=u"Rollpersonerna (Kandor, Zebbe, Navi, Josay och Titziana) är ordensmedlemmar i Yvainorden i staden Yavaris i Banborstland på Pandaros. Yvain är en av de fyra plågade hjältarna och hans ordnar kontrollerar mer eller mindre de civiliserade delarna av kontinenten.")
    cd6k = Campaign.create(name=u"Den Sjätte Konfluxen", world=altor, group=mg, rule_system=u"Fate", description=u"Kampanjen handlar om professor Joseph Tiesen och hans expedition som sägs ha sänts ut av Kublai Shakkar, kejsare och arkon över Mergal. Expeditionen kommer att resa runt i både Jargal och Pandaros i jakt på allt som kan vara relevant för den kommande sjätte konfluxen.")
    kcmp = Campaign.create(name=u"Kult AW", world=kult, group=kg, rule_system=u"AW", description=u"Drama in victorian England at the edge of reality")
    ycmp = Campaign.create(name=u"Yerlog", world=mundana, group=ng, rule_system=u"Eon", description=u"Time to take over the world!")

    s1 = Scene.create(campaign=scmp, name="Intro", order=1)
    s2 = Scene.create(campaign=scmp, name="The old man in the taverna", order=2, parent=s1)
    s3 = Scene.create(campaign=scmp, name="Going to the cave", order=3)
    s4 = Scene.create(campaign=scmp, name="Not finding the way", order=4)
    s5 = Scene.create(campaign=scmp, name="The general comes all over", order=5)

    Session.create(play_start=datetime.datetime(2012,10,20,18,0), play_end=datetime.datetime(2012,10,20,23,0), campaign=scmp, location=u'Snöflingeg')
    Session.create(play_start=datetime.datetime(2012,10,30,18,0), play_end=datetime.datetime(2012,10,30,23,0), campaign=kcmp, location=u'Åby')

    Session.create(play_start=datetime.datetime(2006,07,28,18,0), play_end=datetime.datetime(2006,07,28,23,0), campaign=cd4k, location=u'Snöflingegatan')
    Session.create(play_start=datetime.datetime(2006,07,29,18,0), play_end=datetime.datetime(2006,07,29,23,0), campaign=cd4k, location=u'Snöflingegatan')
    Session.create(play_start=datetime.datetime(2006,07,30,18,0), play_end=datetime.datetime(2006,07,30,23,0), campaign=cd4k, location=u'Snöflingegatan')
    Session.create(play_start=datetime.datetime(2006,12,28,18,0), play_end=datetime.datetime(2006,12,28,23,0), campaign=cd4k, location=u'Mor märtas väg')
    Session.create(play_start=datetime.datetime(2006,12,29,18,0), play_end=datetime.datetime(2006,12,29,23,0), campaign=cd4k, location=u'Mor märtas väg')
    Session.create(play_start=datetime.datetime(2006,12,30,18,0), play_end=datetime.datetime(2006,12,30,23,0), campaign=cd4k, location=u'Persmässvägen')
    Session.create(play_start=datetime.datetime(2007,01,02,18,0), play_end=datetime.datetime(2007,01,02,23,0), campaign=cd4k, location=u'Mjödvägen')
    Session.create(play_start=datetime.datetime(2007,01,03,18,0), play_end=datetime.datetime(2007,01,03,23,0), campaign=cd4k, location=u'Mjödvägen')
    Session.create(play_start=datetime.datetime(2007,01,04,18,0), play_end=datetime.datetime(2007,01,04,23,0), campaign=cd4k, location=u'Storsvängen')
    Session.create(play_start=datetime.datetime(2007,01,05,18,0), play_end=datetime.datetime(2007,01,05,23,0), campaign=cd4k, location=u'Storsvängen')

    Session.create(play_start=datetime.datetime(2009,01,05,18,0), play_end=datetime.datetime(2009,01,05,23,0), campaign=cd6k, location=u'Ulvsbygatan')
    Session.create(play_start=datetime.datetime(2009,01,06,18,0), play_end=datetime.datetime(2009,01,06,23,0), campaign=cd6k, location=u'Ulvsbygatan')
    Session.create(play_start=datetime.datetime(2009,8,9,18,0), play_end=datetime.datetime(2009,8,9,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2009,8,10,18,0), play_end=datetime.datetime(2009,8,10,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2009,8,11,18,0), play_end=datetime.datetime(2009,8,11,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2009,8,12,18,0), play_end=datetime.datetime(2009,8,12,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2010,4,19,18,0), play_end=datetime.datetime(2010,4,19,23,0), campaign=cd6k, location=u'Ulvsbygatan')
    Session.create(play_start=datetime.datetime(2010,4,20,18,0), play_end=datetime.datetime(2010,4,20,23,0), campaign=cd6k, location=u'Ulvsbygatan')
    Session.create(play_start=datetime.datetime(2010,4,21,18,0), play_end=datetime.datetime(2010,4,21,23,0), campaign=cd6k, location=u'Ulvsbygatan')
    Session.create(play_start=datetime.datetime(2010,9,3,18,0), play_end=datetime.datetime(2010,9,3,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2010,9,4,18,0), play_end=datetime.datetime(2010,9,4,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2010,9,5,18,0), play_end=datetime.datetime(2010,9,5,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2011,5,27,18,0), play_end=datetime.datetime(2011,5,27,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2011,5,28,18,0), play_end=datetime.datetime(2011,5,28,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2011,5,29,18,0), play_end=datetime.datetime(2011,5,29,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2011,8,20,18,0), play_end=datetime.datetime(201,8,20,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2011,8,21,18,0), play_end=datetime.datetime(201,8,21,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2011,8,22,18,0), play_end=datetime.datetime(201,8,22,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2011,8,24,18,0), play_end=datetime.datetime(201,8,24,23,0), campaign=cd6k, location=u'Olsäter')
    Session.create(play_start=datetime.datetime(2012,1,27,18,0), play_end=datetime.datetime(2012,1,27,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,1,28,18,0), play_end=datetime.datetime(2012,1,28,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,1,29,18,0), play_end=datetime.datetime(2012,1,29,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,4,28,18,0), play_end=datetime.datetime(2012,4,28,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,4,29,18,0), play_end=datetime.datetime(2012,4,29,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,8,31,18,0), play_end=datetime.datetime(2012,8,31,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,9,1,18,0), play_end=datetime.datetime(2012,9,1,23,0), campaign=cd6k, location=u'Mölndalsvägen')
    Session.create(play_start=datetime.datetime(2012,9,2,18,0), play_end=datetime.datetime(2012,9,2,23,0), campaign=cd6k, location=u'Mölndalsvägen')

    StringGenerator.drop_table(fail_silently=True)
    StringGenerator.create_table()
    StringGenerator.create(name="Default Generator")
    
    GeneratorInputList.drop_table(fail_silently=True)
    GeneratorInputList.create_table()
    GeneratorInputItem.drop_table(fail_silently=True)
    GeneratorInputItem.create_table()
    
    gil1 = GeneratorInputList.create(name=u'Korhiv start letter')
    gil2 = GeneratorInputList.create(name=u'Korhiv middle syllables')
    gil3 = GeneratorInputList.create(name=u'Korhiv end syllables')
    
    GeneratorInputItem.create(input_list=gil1, content=u'b')
    GeneratorInputItem.create(input_list=gil1, content=u'ch')
    GeneratorInputItem.create(input_list=gil1, content=u'd')
    GeneratorInputItem.create(input_list=gil1, content=u'f')
    GeneratorInputItem.create(input_list=gil1, content=u'g')
    GeneratorInputItem.create(input_list=gil1, content=u'h')
    GeneratorInputItem.create(input_list=gil1, content=u'j\'')
    GeneratorInputItem.create(input_list=gil1, content=u'k\'')
    GeneratorInputItem.create(input_list=gil1, content=u'm')
    GeneratorInputItem.create(input_list=gil1, content=u'n')
    GeneratorInputItem.create(input_list=gil1, content=u'r')
    GeneratorInputItem.create(input_list=gil1, content=u'sh')
    GeneratorInputItem.create(input_list=gil1, content=u't')
    GeneratorInputItem.create(input_list=gil1, content=u'v')
    GeneratorInputItem.create(input_list=gil1, content=u'y')
    GeneratorInputItem.create(input_list=gil1, content=u'z')

    GeneratorInputItem.create(input_list=gil2, content=u'ab')
    GeneratorInputItem.create(input_list=gil2, content=u'ach')
    GeneratorInputItem.create(input_list=gil2, content=u'ad')
    GeneratorInputItem.create(input_list=gil2, content=u'af')
    GeneratorInputItem.create(input_list=gil2, content=u'ag')
    GeneratorInputItem.create(input_list=gil2, content=u'ah')
    GeneratorInputItem.create(input_list=gil2, content=u'al\'')
    GeneratorInputItem.create(input_list=gil2, content=u'am')
    GeneratorInputItem.create(input_list=gil2, content=u'an')
    GeneratorInputItem.create(input_list=gil2, content=u'aq')
    GeneratorInputItem.create(input_list=gil2, content=u'ar')
    GeneratorInputItem.create(input_list=gil2, content=u'ash')
    GeneratorInputItem.create(input_list=gil2, content=u'at')
    GeneratorInputItem.create(input_list=gil2, content=u'av')
    GeneratorInputItem.create(input_list=gil2, content=u'ay')
    GeneratorInputItem.create(input_list=gil2, content=u'az')
    GeneratorInputItem.create(input_list=gil2, content=u'eb')
    GeneratorInputItem.create(input_list=gil2, content=u'ech')
    GeneratorInputItem.create(input_list=gil2, content=u'ed')
    GeneratorInputItem.create(input_list=gil2, content=u'eh')
    GeneratorInputItem.create(input_list=gil2, content=u'el')
    GeneratorInputItem.create(input_list=gil2, content=u'em')
    GeneratorInputItem.create(input_list=gil2, content=u'en')
    GeneratorInputItem.create(input_list=gil2, content=u'er')
    GeneratorInputItem.create(input_list=gil2, content=u'esh')
    GeneratorInputItem.create(input_list=gil2, content=u'ev')
    GeneratorInputItem.create(input_list=gil2, content=u'ey')
    GeneratorInputItem.create(input_list=gil2, content=u'ez')
    GeneratorInputItem.create(input_list=gil2, content=u'ib')
    GeneratorInputItem.create(input_list=gil2, content=u'ich')
    GeneratorInputItem.create(input_list=gil2, content=u'id')
    GeneratorInputItem.create(input_list=gil2, content=u'if')
    GeneratorInputItem.create(input_list=gil2, content=u'ig')
    GeneratorInputItem.create(input_list=gil2, content=u'ih')
    GeneratorInputItem.create(input_list=gil2, content=u'il')
    GeneratorInputItem.create(input_list=gil2, content=u'im')
    GeneratorInputItem.create(input_list=gil2, content=u'in')
    GeneratorInputItem.create(input_list=gil2, content=u'iq')
    GeneratorInputItem.create(input_list=gil2, content=u'ir\'')
    GeneratorInputItem.create(input_list=gil2, content=u'ish')
    GeneratorInputItem.create(input_list=gil2, content=u'iv')
    GeneratorInputItem.create(input_list=gil2, content=u'iy')
    GeneratorInputItem.create(input_list=gil2, content=u'iz')
    GeneratorInputItem.create(input_list=gil2, content=u'od')
    GeneratorInputItem.create(input_list=gil2, content=u'or\'')
    GeneratorInputItem.create(input_list=gil2, content=u'oz')
    GeneratorInputItem.create(input_list=gil2, content=u'um')
    GeneratorInputItem.create(input_list=gil2, content=u'ûn')

    GeneratorInputItem.create(input_list=gil3, content=u'ab')
    GeneratorInputItem.create(input_list=gil3, content=u'ach')
    GeneratorInputItem.create(input_list=gil3, content=u'ad')
    GeneratorInputItem.create(input_list=gil3, content=u'af')
    GeneratorInputItem.create(input_list=gil3, content=u'ag')
    GeneratorInputItem.create(input_list=gil3, content=u'ah')
    GeneratorInputItem.create(input_list=gil3, content=u'al')
    GeneratorInputItem.create(input_list=gil3, content=u'am')
    GeneratorInputItem.create(input_list=gil3, content=u'ân')
    GeneratorInputItem.create(input_list=gil3, content=u'aq')
    GeneratorInputItem.create(input_list=gil3, content=u'ar')
    GeneratorInputItem.create(input_list=gil3, content=u'ash')
    GeneratorInputItem.create(input_list=gil3, content=u'at')
    GeneratorInputItem.create(input_list=gil3, content=u'av')
    GeneratorInputItem.create(input_list=gil3, content=u'ay')
    GeneratorInputItem.create(input_list=gil3, content=u'az')
    GeneratorInputItem.create(input_list=gil3, content=u'êb')
    GeneratorInputItem.create(input_list=gil3, content=u'ech')
    GeneratorInputItem.create(input_list=gil3, content=u'êd')
    GeneratorInputItem.create(input_list=gil3, content=u'eh')
    GeneratorInputItem.create(input_list=gil3, content=u'el')
    GeneratorInputItem.create(input_list=gil3, content=u'em')
    GeneratorInputItem.create(input_list=gil3, content=u'en')
    GeneratorInputItem.create(input_list=gil3, content=u'er')
    GeneratorInputItem.create(input_list=gil3, content=u'esh')
    GeneratorInputItem.create(input_list=gil3, content=u'ev')
    GeneratorInputItem.create(input_list=gil3, content=u'ey')
    GeneratorInputItem.create(input_list=gil3, content=u'ez')
    GeneratorInputItem.create(input_list=gil3, content=u'îb')
    GeneratorInputItem.create(input_list=gil3, content=u'ich')
    GeneratorInputItem.create(input_list=gil3, content=u'îd')
    GeneratorInputItem.create(input_list=gil3, content=u'if')
    GeneratorInputItem.create(input_list=gil3, content=u'ig')
    GeneratorInputItem.create(input_list=gil3, content=u'ih')
    GeneratorInputItem.create(input_list=gil3, content=u'il')
    GeneratorInputItem.create(input_list=gil3, content=u'im')
    GeneratorInputItem.create(input_list=gil3, content=u'în')
    GeneratorInputItem.create(input_list=gil3, content=u'iq')
    GeneratorInputItem.create(input_list=gil3, content=u'ir')
    GeneratorInputItem.create(input_list=gil3, content=u'ish')
    GeneratorInputItem.create(input_list=gil3, content=u'iv')
    GeneratorInputItem.create(input_list=gil3, content=u'iy')
    GeneratorInputItem.create(input_list=gil3, content=u'iz')
    GeneratorInputItem.create(input_list=gil3, content=u'od')
    GeneratorInputItem.create(input_list=gil3, content=u'or')
    GeneratorInputItem.create(input_list=gil3, content=u'oz')
    GeneratorInputItem.create(input_list=gil3, content=u'um')
    GeneratorInputItem.create(input_list=gil3, content=u'ûn')
