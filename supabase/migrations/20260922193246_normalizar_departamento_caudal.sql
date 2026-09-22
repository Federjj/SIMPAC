-- ANA escribe algunos departamentos sin tilde o con otra capitalización. La ingesta
-- ya los normaliza al guardar (backend/ingesta/departamentos.py); esto corrige las
-- lecturas anteriores para que caudal_actual no mezcle "Huanuco" con "Huánuco".
update public.lectura_caudal set departamento = case departamento
    when 'Apurimac'      then 'Apurímac'
    when 'Huanuco'       then 'Huánuco'
    when 'Junin'         then 'Junín'
    when 'Madre De Dios' then 'Madre de Dios'
    when 'San Martin'    then 'San Martín'
  end
where departamento in ('Apurimac', 'Huanuco', 'Junin', 'Madre De Dios', 'San Martin');
